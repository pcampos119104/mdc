"""Consolidate approved legacy sources into reviewable Django fixture artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from apps.members.models import Member

from .normalization import (
    brazilian_state_to_uf,
    clean_preserved_text,
    comparison_key,
    normalize_cep,
    normalize_cpf,
    normalize_email,
    normalize_phone,
    parse_brazilian_date,
)
from .pdf import read_pdf, stage_pdf_photo
from .records import (
    PDFReadResult,
    PDFRecord,
    PDFSourceKind,
    PhotoStageStatus,
    SourceIssue,
    SpreadsheetRecord,
)
from .spreadsheet import SpreadsheetReadError, read_spreadsheet


class ConsolidationError(ValueError):
    """Report an input or output condition that prevents safe consolidation."""


@dataclass(frozen=True, slots=True)
class _Match:
    """Represent one safe source-to-source association before field mapping."""

    spreadsheet: SpreadsheetRecord
    pdf_result: PDFReadResult
    rule: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConsolidationResult:
    """Describe generated artifact paths and their aggregate summary."""

    fixture_path: Path
    report_path: Path
    summary_path: Path
    photo_manifest_path: Path
    staged_photos_path: Path
    summary: dict[str, int]


_REGISTRATION_TYPES = {
    "pessoa": Member.RegistrationType.MEMBER,
    "lideranca": Member.RegistrationType.LEADERSHIP,
    "pastor": Member.RegistrationType.PASTOR,
}
_CLASSIFICATIONS = {
    "voluntariado": Member.Classification.VOLUNTEER,
    "comunakids": Member.Classification.COMUNAKIDS,
    "jovens": Member.Classification.YOUTH,
    "louvor": Member.Classification.WORSHIP,
    "someimagem": Member.Classification.SOUND_AND_MEDIA,
    "teatro": Member.Classification.THEATER,
}
_SEXES = {
    "masculino": Member.Sex.MALE,
    "feminino": Member.Sex.FEMALE,
}
_MARITAL_STATUSES = {
    "solteiroa": Member.MaritalStatus.SINGLE,
    "casadoa": Member.MaritalStatus.MARRIED,
    "uniaoestavel": Member.MaritalStatus.STABLE_UNION,
    "divorciadoa": Member.MaritalStatus.DIVORCED,
    "viuvoa": Member.MaritalStatus.WIDOWED,
}
_BLOCKING_PDF_WARNING_CODES = {"missing_label", "ambiguous_label"}
_BIG_AUTO_FIELD_MAX = 2**63 - 1
_MEMBER_FIELD_LIMITS = {
    "name": 255,
    "photo": 100,
    "registration_type": 20,
    "cpf": 11,
    "sex": 6,
    "birthplace": 255,
    "profession": 255,
    "email": 254,
    "phone": 15,
    "father_name": 255,
    "mother_name": 255,
    "spouse_name": 255,
    "marital_status": 20,
}
_ADDRESS_FIELD_LIMITS = {
    "postal_code": 8,
    "state": 2,
    "city": 100,
    "street": 255,
    "street_number": 30,
    "complement": 255,
    "district": 255,
}


def _compact_key(value: object | None) -> str:
    """Return a comparison key that also tolerates PDF letter spacing."""
    return comparison_key(value).replace(" ", "")


def _first_nonblank(*values: object | None) -> str:
    """Return the first source value containing non-whitespace text."""
    for value in values:
        cleaned = clean_preserved_text(value)
        if cleaned:
            return cleaned
    return ""


def _hash_file(path: Path) -> str:
    """Return the SHA256 digest for one source or generated file."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_timestamp(path: Path, explicit: str | None) -> str:
    """Return a deterministic UTC timestamp from an override or XLSX metadata."""
    raw_timestamp = explicit
    if raw_timestamp is None:
        try:
            with ZipFile(path) as archive:
                core = ElementTree.fromstring(archive.read("docProps/core.xml"))
        except (BadZipFile, KeyError, OSError, ElementTree.ParseError) as exc:
            raise ConsolidationError(
                "XLSX creation metadata is unavailable; provide --snapshot-timestamp."
            ) from exc
        created = next(
            (
                element.text
                for element in core.iter()
                if element.tag.rsplit("}", 1)[-1] == "created" and element.text
            ),
            None,
        )
        if created is None:
            raise ConsolidationError(
                "XLSX creation metadata is unavailable; provide --snapshot-timestamp."
            )
        raw_timestamp = created

    try:
        parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConsolidationError("Snapshot timestamp must be a valid ISO datetime.") from exc
    if parsed.tzinfo is None:
        raise ConsolidationError("Snapshot timestamp must include a UTC offset.")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _issue_payload(issue: SourceIssue) -> dict[str, object]:
    """Serialize one source issue without exposing absolute workstation paths."""
    return {
        "source_file": issue.source_path.name,
        "source_row": issue.source_row,
        "field": issue.field,
        "code": issue.code,
        "severity": issue.severity,
        "message": issue.message,
        "raw_value": issue.raw_value,
    }


def _pdf_blocks_automatic_match(result: PDFReadResult) -> bool:
    """Return whether parser evidence is insufficient for automatic matching."""
    return result.record is None or any(
        issue.severity == "error" or issue.code in _BLOCKING_PDF_WARNING_CODES
        for issue in result.issues
    )


def _normalized_equal(
    left: object | None,
    right: object | None,
    normalizer: Callable[[object | None], object | None],
) -> bool:
    """Compare two populated source values through one semantic normalizer."""
    if not clean_preserved_text(left) or not clean_preserved_text(right):
        return False
    normalized_left = normalizer(left)
    normalized_right = normalizer(right)
    return normalized_left is not None and normalized_left == normalized_right


def _overlap_conflicts(
    spreadsheet: SpreadsheetRecord, pdf: PDFRecord
) -> list[dict[str, str]]:
    """Return populated overlapping fields that disagree semantically."""
    comparisons = (
        ("name", spreadsheet.name_raw, pdf.name_raw, comparison_key),
        (
            "identification",
            spreadsheet.identification_raw,
            pdf.identification_raw,
            comparison_key,
        ),
        (
            "registration_type",
            spreadsheet.person_type_raw,
            pdf.registration_type_raw,
            _compact_key,
        ),
        (
            "member_type",
            spreadsheet.member_type_raw,
            pdf.person_type_raw,
            _compact_key,
        ),
        ("email", spreadsheet.email_raw, pdf.email_raw, normalize_email),
        (
            "mobile_phone",
            spreadsheet.mobile_phone_raw,
            pdf.mobile_phone_raw,
            normalize_phone,
        ),
        (
            "home_phone",
            spreadsheet.home_phone_raw,
            pdf.home_phone_raw,
            normalize_phone,
        ),
        ("street", spreadsheet.street_raw, pdf.street_raw, comparison_key),
        (
            "street_number",
            spreadsheet.street_number_raw,
            pdf.street_number_raw,
            comparison_key,
        ),
        (
            "complement",
            spreadsheet.complement_raw,
            pdf.complement_raw,
            comparison_key,
        ),
        ("district", spreadsheet.district_raw, pdf.district_raw, comparison_key),
        ("city", spreadsheet.city_raw, pdf.city_raw, comparison_key),
        ("state", spreadsheet.state_raw, pdf.state_raw, brazilian_state_to_uf),
    )
    conflicts: list[dict[str, str]] = []
    for field, left, right, normalizer in comparisons:
        if not clean_preserved_text(left) or not clean_preserved_text(right):
            continue
        if not _normalized_equal(left, right, normalizer):
            conflicts.append(
                {
                    "field": field,
                    "spreadsheet_value": clean_preserved_text(left),
                    "pdf_value": clean_preserved_text(right),
                }
            )

    pdf_birth_date = parse_brazilian_date(pdf.birth_date_raw)
    if spreadsheet.birth_date and pdf.birth_date_raw and (
        pdf_birth_date is None or spreadsheet.birth_date != pdf_birth_date
    ):
        conflicts.append(
            {
                "field": "birth_date",
                "spreadsheet_value": spreadsheet.birth_date.isoformat(),
                "pdf_value": clean_preserved_text(pdf.birth_date_raw),
            }
        )
    return conflicts


def _matching_evidence(
    spreadsheet: SpreadsheetRecord, pdf: PDFRecord
) -> tuple[str, ...]:
    """Return independent exact evidence shared by both sources."""
    evidence: list[str] = []
    pdf_birth_date = parse_brazilian_date(pdf.birth_date_raw)
    if spreadsheet.birth_date and spreadsheet.birth_date == pdf_birth_date:
        evidence.append("birth_date")
    if _normalized_equal(spreadsheet.email_raw, pdf.email_raw, normalize_email):
        evidence.append("email")
    if _normalized_equal(
        spreadsheet.mobile_phone_raw, pdf.mobile_phone_raw, normalize_phone
    ):
        evidence.append("mobile_phone")

    address_pairs = (
        (spreadsheet.street_raw, pdf.street_raw),
        (spreadsheet.street_number_raw, pdf.street_number_raw),
        (spreadsheet.city_raw, pdf.city_raw),
    )
    if all(
        _normalized_equal(left, right, comparison_key)
        for left, right in address_pairs
    ):
        evidence.append("address")
    return tuple(evidence)


def _candidate_payload(result: PDFReadResult, spreadsheet_name: str) -> dict[str, object]:
    """Return stable candidate information suitable for manual review."""
    internal_name = result.record.name_raw if result.record else ""
    score = SequenceMatcher(
        None, comparison_key(spreadsheet_name), comparison_key(internal_name)
    ).ratio()
    return {
        "pdf_file": result.source_path.name,
        "pdf_ordinal": result.source.ordinal,
        "internal_name": internal_name,
        "name_similarity": round(score, 4),
    }


def _review_payload(
    spreadsheet: SpreadsheetRecord,
    *,
    reason_codes: list[str],
    candidates: list[PDFReadResult],
    conflicts: list[dict[str, str]] | None = None,
    source_issues: list[SourceIssue] | None = None,
    confidence: str = "none",
) -> dict[str, object]:
    """Build one deterministic manual-review record."""
    ranked_candidates = sorted(
        (_candidate_payload(candidate, spreadsheet.name_raw) for candidate in candidates),
        key=lambda item: (
            -float(str(item["name_similarity"])),
            item["pdf_ordinal"] if item["pdf_ordinal"] is not None else 10**9,
            str(item["pdf_file"]),
        ),
    )[:3]
    return {
        "source_row": spreadsheet.source_row,
        "source_ordinal": spreadsheet.ordinal,
        "spreadsheet_name": clean_preserved_text(spreadsheet.name_raw),
        "confidence": confidence,
        "reason_codes": sorted(set(reason_codes)),
        "pdf_candidates": ranked_candidates,
        "conflicts": conflicts or [],
        "source_issues": [
            _issue_payload(issue)
            for issue in sorted(
                source_issues or [],
                key=lambda item: (item.code, item.field or "", item.message),
            )
        ],
    }


def _match_sources(
    spreadsheet_records: tuple[SpreadsheetRecord, ...],
    pdf_results: list[PDFReadResult],
    spreadsheet_issues: tuple[SourceIssue, ...],
) -> tuple[list[_Match], list[dict[str, object]]]:
    """Apply approved high-confidence rules and report every unsafe association."""
    members = [
        result
        for result in pdf_results
        if result.source.kind in {PDFSourceKind.MEMBER, PDFSourceKind.UNKNOWN}
    ]
    by_ordinal: dict[int, list[PDFReadResult]] = defaultdict(list)
    by_name: dict[str, list[PDFReadResult]] = defaultdict(list)
    for result in members:
        if result.source.ordinal is not None:
            by_ordinal[result.source.ordinal].append(result)
        if result.record and result.record.name_raw:
            by_name[comparison_key(result.record.name_raw)].append(result)

    spreadsheet_issues_by_row: dict[int, list[SourceIssue]] = defaultdict(list)
    for issue in spreadsheet_issues:
        if issue.source_row is not None:
            spreadsheet_issues_by_row[issue.source_row].append(issue)

    proposed: list[_Match] = []
    reviews: list[dict[str, object]] = []
    for spreadsheet in spreadsheet_records:
        row_issues = spreadsheet_issues_by_row.get(spreadsheet.source_row, [])
        if any(issue.severity == "error" for issue in row_issues):
            reviews.append(
                _review_payload(
                    spreadsheet,
                    reason_codes=["spreadsheet_parse_error"],
                    candidates=by_ordinal.get(spreadsheet.ordinal, []),
                    source_issues=row_issues,
                )
            )
            continue

        ordinal_candidates = by_ordinal.get(spreadsheet.ordinal, [])
        if len(ordinal_candidates) > 1:
            reviews.append(
                _review_payload(
                    spreadsheet,
                    reason_codes=["duplicate_pdf_ordinal"],
                    candidates=ordinal_candidates,
                    confidence="low",
                )
            )
            continue

        if len(ordinal_candidates) == 1:
            candidate = ordinal_candidates[0]
            candidate_issues = list(candidate.issues)
            if candidate.record is None or _pdf_blocks_automatic_match(candidate):
                reviews.append(
                    _review_payload(
                        spreadsheet,
                        reason_codes=["pdf_parse_issue"],
                        candidates=[candidate],
                        source_issues=candidate_issues,
                        confidence="medium",
                    )
                )
                continue

            conflicts = _overlap_conflicts(spreadsheet, candidate.record)
            same_name = comparison_key(spreadsheet.name_raw) == comparison_key(
                candidate.record.name_raw
            )
            evidence = _matching_evidence(spreadsheet, candidate.record)
            reason_codes: list[str] = []
            if not same_name:
                reason_codes.append("internal_name_mismatch")
            if not evidence:
                reason_codes.append("missing_corroborating_evidence")
            if conflicts:
                reason_codes.append("source_conflict")
            if reason_codes:
                reviews.append(
                    _review_payload(
                        spreadsheet,
                        reason_codes=reason_codes,
                        candidates=[candidate],
                        conflicts=conflicts,
                        source_issues=candidate_issues,
                        confidence="medium" if same_name else "low",
                    )
                )
                continue
            proposed.append(_Match(spreadsheet, candidate, "H1", evidence))
            continue

        exact_name_candidates = by_name.get(comparison_key(spreadsheet.name_raw), [])
        safe_secondary: list[tuple[PDFReadResult, tuple[str, ...]]] = []
        for candidate in exact_name_candidates:
            if candidate.source.ordinal not in {None, spreadsheet.ordinal}:
                continue
            if candidate.record is None or _pdf_blocks_automatic_match(candidate):
                continue
            if _overlap_conflicts(spreadsheet, candidate.record):
                continue
            evidence = _matching_evidence(spreadsheet, candidate.record)
            if "birth_date" in evidence and len(evidence) >= 2:
                safe_secondary.append((candidate, evidence))
        if len(safe_secondary) == 1:
            candidate, evidence = safe_secondary[0]
            proposed.append(_Match(spreadsheet, candidate, "H2", evidence))
            continue

        suggested = exact_name_candidates or sorted(
            members,
            key=lambda result: (
                -SequenceMatcher(
                    None,
                    comparison_key(spreadsheet.name_raw),
                    comparison_key(result.record.name_raw if result.record else ""),
                ).ratio(),
                result.source.ordinal if result.source.ordinal is not None else 10**9,
            ),
        )[:3]
        reviews.append(
            _review_payload(
                spreadsheet,
                reason_codes=[
                    "ambiguous_secondary_match"
                    if len(safe_secondary) > 1
                    else "pdf_not_matched"
                ],
                candidates=suggested,
                confidence="medium" if exact_name_candidates else "low",
            )
        )

    matches_by_pdf: dict[Path, list[_Match]] = defaultdict(list)
    for match in proposed:
        matches_by_pdf[match.pdf_result.source_path].append(match)
    accepted: list[_Match] = []
    for match in proposed:
        duplicates = matches_by_pdf[match.pdf_result.source_path]
        if len(duplicates) == 1:
            accepted.append(match)
            continue
        reviews.append(
            _review_payload(
                match.spreadsheet,
                reason_codes=["pdf_claimed_by_multiple_rows"],
                candidates=[match.pdf_result],
                confidence="medium",
            )
        )
    return accepted, sorted(reviews, key=lambda item: int(str(item["source_row"])))


def _validation_error(field: str, code: str, raw_value: object) -> dict[str, str]:
    """Build one field-level transformation error for manual review."""
    return {
        "field": field,
        "code": code,
        "raw_value": clean_preserved_text(raw_value),
    }


def _validate_lengths(
    fields: dict[str, object], limits: dict[str, int], errors: list[dict[str, str]]
) -> None:
    """Append errors for generated strings exceeding model field limits."""
    for field, limit in limits.items():
        value = fields.get(field)
        if isinstance(value, str) and len(value) > limit:
            errors.append(_validation_error(field, "max_length_exceeded", value))


def _mapped_record(
    match: _Match, pk: int, timestamp: str
) -> tuple[dict[str, object], dict[str, object], list[dict[str, str]], list[str]]:
    """Map one safe source match to explicit Member and Address fixture fields."""
    spreadsheet = match.spreadsheet
    pdf = match.pdf_result.record
    if pdf is None:
        raise AssertionError("Accepted matches must contain a parsed PDF record.")

    errors: list[dict[str, str]] = []
    warnings: list[str] = []
    name = clean_preserved_text(spreadsheet.name_raw)
    registration_key = _compact_key(spreadsheet.person_type_raw)
    registration_type = _REGISTRATION_TYPES.get(registration_key)
    if registration_type is None:
        errors.append(
            _validation_error(
                "registration_type", "unknown_choice", spreadsheet.person_type_raw
            )
        )
        registration_type = Member.RegistrationType.MEMBER

    classification_key = _compact_key(spreadsheet.member_type_raw)
    classification = _CLASSIFICATIONS.get(classification_key)
    classifications = [classification] if classification else []
    if clean_preserved_text(spreadsheet.member_type_raw) and not classification:
        warnings.append("unmapped_member_type")

    cpf = None
    if clean_preserved_text(pdf.cpf_raw):
        cpf = normalize_cpf(pdf.cpf_raw)
        if cpf is None:
            errors.append(_validation_error("cpf", "invalid_cpf", pdf.cpf_raw))

    pdf_birth_date = parse_brazilian_date(pdf.birth_date_raw)
    if pdf.birth_date_raw and pdf_birth_date is None:
        errors.append(
            _validation_error("birth_date", "invalid_date", pdf.birth_date_raw)
        )
    birth_date = spreadsheet.birth_date or pdf_birth_date

    baptism_dates = {
        occurrence.occurrence_date
        for occurrence in pdf.occurrences
        if _compact_key(occurrence.occurrence_type_raw) == "batismo"
    }
    baptism_date = next(iter(baptism_dates)) if len(baptism_dates) == 1 else None
    if len(baptism_dates) > 1:
        errors.append(
            _validation_error(
                "baptism_date", "conflicting_baptism_dates", ", ".join(
                    sorted(value.isoformat() for value in baptism_dates)
                )
            )
        )

    sex = ""
    if clean_preserved_text(pdf.sex_raw):
        sex = _SEXES.get(_compact_key(pdf.sex_raw), "")
        if not sex:
            errors.append(_validation_error("sex", "unknown_choice", pdf.sex_raw))

    email_raw = _first_nonblank(spreadsheet.email_raw, pdf.email_raw)
    email = clean_preserved_text(email_raw)
    if email and normalize_email(email) is None:
        errors.append(_validation_error("email", "invalid_email", email_raw))

    phone_sources = (
        pdf.mobile_phone_raw,
        spreadsheet.mobile_phone_raw,
        spreadsheet.home_phone_raw,
        pdf.home_phone_raw,
        spreadsheet.work_phone_raw,
        spreadsheet.contact_phone_raw,
    )
    phone = ""
    for raw_phone in phone_sources:
        if not clean_preserved_text(raw_phone):
            continue
        normalized_phone = normalize_phone(raw_phone)
        if normalized_phone is None:
            errors.append(_validation_error("phone", "invalid_phone", raw_phone))
            continue
        phone = normalized_phone
        break
    informed_phones = {
        normalized
        for raw_phone in phone_sources
        if (normalized := normalize_phone(raw_phone)) is not None
    }
    if len(informed_phones) > 1:
        warnings.append("additional_phone_not_imported")

    marital_status = ""
    if clean_preserved_text(pdf.marital_status_raw):
        marital_status = _MARITAL_STATUSES.get(
            _compact_key(pdf.marital_status_raw), ""
        )
        if not marital_status:
            warnings.append("unmapped_marital_status")

    member_fields: dict[str, object] = {
        "deleted_at": None,
        "name": name,
        "photo": "",
        "registration_type": registration_type,
        "classifications": classifications,
        "cpf": cpf,
        "birth_date": birth_date.isoformat() if birth_date else None,
        "baptism_date": baptism_date.isoformat() if baptism_date else None,
        "acclamation_date": None,
        "include_in_birthday_list": True,
        "sex": sex,
        "birthplace": clean_preserved_text(pdf.birthplace_raw),
        "profession": "",
        "email": email,
        "phone": phone,
        "father_name": clean_preserved_text(pdf.father_name_raw),
        "mother_name": clean_preserved_text(pdf.mother_name_raw),
        "spouse_name": clean_preserved_text(pdf.spouse_name_raw),
        "marital_status": marital_status,
        "marriage_date": None,
        "is_active": True,
        "inactive_reason": "",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    if not name:
        errors.append(_validation_error("name", "required", name))

    postal_code = ""
    if clean_preserved_text(pdf.postal_code_raw):
        postal_code = normalize_cep(pdf.postal_code_raw) or ""
        if not postal_code:
            errors.append(
                _validation_error(
                    "postal_code", "invalid_postal_code", pdf.postal_code_raw
                )
            )

    state_raw = _first_nonblank(spreadsheet.state_raw, pdf.state_raw)
    state = brazilian_state_to_uf(state_raw) or ""
    if clean_preserved_text(state_raw) and not state:
        errors.append(_validation_error("state", "invalid_state", state_raw))

    address_fields: dict[str, object] = {
        "member": pk,
        "postal_code": postal_code,
        "state": state,
        "city": _first_nonblank(spreadsheet.city_raw, pdf.city_raw),
        "street": _first_nonblank(spreadsheet.street_raw, pdf.street_raw),
        "street_number": _first_nonblank(
            pdf.street_number_raw, spreadsheet.street_number_raw
        ),
        "complement": _first_nonblank(
            spreadsheet.complement_raw, pdf.complement_raw
        ),
        "district": _first_nonblank(spreadsheet.district_raw, pdf.district_raw),
    }
    _validate_lengths(member_fields, _MEMBER_FIELD_LIMITS, errors)
    _validate_lengths(address_fields, _ADDRESS_FIELD_LIMITS, errors)
    return member_fields, address_fields, errors, sorted(set(warnings))


def _write_json(path: Path, payload: object) -> None:
    """Write deterministic UTF-8 JSON to a new private file."""
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        output.write(content)


def _review_has_reason(review: dict[str, object], reason: str) -> bool:
    """Return whether a manual-review entry contains one reason code."""
    reason_codes = review.get("reason_codes")
    return isinstance(reason_codes, list) and reason in reason_codes


def _prepare_output_directory(output_directory: Path) -> Path:
    """Create or validate an empty private output directory."""
    if output_directory.exists():
        if not output_directory.is_dir() or output_directory.is_symlink():
            raise ConsolidationError("Output path must be a real directory.")
        if any(output_directory.iterdir()):
            raise ConsolidationError("Output directory must be empty.")
    else:
        output_directory.mkdir(parents=True, mode=0o700)
    staged = output_directory / "staged_photos"
    staged.mkdir(mode=0o700)
    return staged


def _unmapped_source_summary(
    spreadsheet_records: tuple[SpreadsheetRecord, ...], pdf_results: list[PDFReadResult]
) -> dict[str, object]:
    """Summarize source values intentionally unsupported by the current model."""
    member_types = Counter(
        clean_preserved_text(record.member_type_raw)
        for record in spreadsheet_records
        if _compact_key(record.member_type_raw) not in _CLASSIFICATIONS
    )
    marital_statuses = Counter(
        clean_preserved_text(result.record.marital_status_raw)
        for result in pdf_results
        if result.record
        and result.record.marital_status_raw
        and _compact_key(result.record.marital_status_raw) not in _MARITAL_STATUSES
    )
    occurrences = Counter(
        clean_preserved_text(occurrence.occurrence_type_raw)
        for result in pdf_results
        if result.record
        for occurrence in result.record.occurrences
        if _compact_key(occurrence.occurrence_type_raw) != "batismo"
    )
    return {
        "member_type_values": dict(sorted(member_types.items())),
        "marital_status_values": dict(sorted(marital_statuses.items())),
        "non_baptism_occurrences": dict(sorted(occurrences.items())),
        "group_participation_populated": sum(
            bool(clean_preserved_text(record.group_participation_raw))
            for record in spreadsheet_records
        ),
        "nationality_populated": sum(
            bool(clean_preserved_text(result.record.nationality_raw))
            for result in pdf_results
            if result.record
        ),
        "country_populated": sum(
            bool(clean_preserved_text(result.record.country_raw))
            for result in pdf_results
            if result.record
        ),
        "contact_name_populated": sum(
            bool(clean_preserved_text(result.record.contact_name_raw))
            for result in pdf_results
            if result.record
        ),
        "work_phone_populated": sum(
            bool(clean_preserved_text(record.work_phone_raw))
            for record in spreadsheet_records
        ),
        "contact_phone_populated": sum(
            bool(clean_preserved_text(record.contact_phone_raw))
            for record in spreadsheet_records
        ),
    }


def consolidate_legacy_members(
    *,
    spreadsheet_path: str | Path,
    pdf_directory: str | Path,
    output_directory: str | Path,
    pk_base: int,
    snapshot_timestamp: str | None = None,
) -> ConsolidationResult:
    """Generate a fixture, review report, summary, and staged photo manifest."""
    spreadsheet_path = Path(spreadsheet_path)
    pdf_directory = Path(pdf_directory)
    output_directory = Path(output_directory)
    if isinstance(pk_base, bool) or pk_base < 1:
        raise ConsolidationError("PK base must be a positive integer.")
    if not pdf_directory.is_dir() or pdf_directory.is_symlink():
        raise ConsolidationError("PDF source path must be a real directory.")
    unavailable_tools = [
        executable
        for executable in ("pdftotext", "pdfimages", "pdftohtml")
        if shutil.which(executable) is None
    ]
    if unavailable_tools:
        raise ConsolidationError(
            "Required Poppler tools are unavailable: " + ", ".join(unavailable_tools)
        )

    timestamp = _snapshot_timestamp(spreadsheet_path, snapshot_timestamp)
    try:
        spreadsheet = read_spreadsheet(spreadsheet_path)
    except SpreadsheetReadError as exc:
        raise ConsolidationError(str(exc)) from exc

    maximum_ordinal = max(
        (record.ordinal for record in spreadsheet.records), default=0
    )
    if maximum_ordinal and pk_base > _BIG_AUTO_FIELD_MAX - maximum_ordinal + 1:
        raise ConsolidationError("PK range exceeds the signed BigAutoField limit.")

    pdf_paths = sorted(
        (
            path
            for path in pdf_directory.iterdir()
            if path.is_file() and path.suffix.casefold() == ".pdf"
        ),
        key=lambda path: (path.name.casefold(), path.name),
    )
    if not pdf_paths:
        raise ConsolidationError("PDF source directory contains no PDF files.")
    pdf_results = [read_pdf(path) for path in pdf_paths]
    matches, reviews = _match_sources(
        spreadsheet.records, pdf_results, spreadsheet.issues
    )

    mapped: list[
        tuple[_Match, int, dict[str, object], dict[str, object], list[str]]
    ] = []
    for match in matches:
        pk = pk_base + match.spreadsheet.ordinal - 1
        member_fields, address_fields, errors, warnings = _mapped_record(
            match, pk, timestamp
        )
        if errors:
            reviews.append(
                _review_payload(
                    match.spreadsheet,
                    reason_codes=["mapping_validation_error"],
                    candidates=[match.pdf_result],
                    confidence="high",
                )
                | {"validation_errors": errors}
            )
            continue
        mapped.append((match, pk, member_fields, address_fields, warnings))

    duplicate_cpfs = {
        cpf
        for cpf, count in Counter(
            member_fields["cpf"]
            for _match, _pk, member_fields, _address, _warnings in mapped
            if member_fields["cpf"]
        ).items()
        if count > 1
    }
    final_mapped = []
    for item in mapped:
        match, _pk, member_fields, _address_fields, _warnings = item
        if member_fields["cpf"] in duplicate_cpfs:
            reviews.append(
                _review_payload(
                    match.spreadsheet,
                    reason_codes=["duplicate_cpf_in_output"],
                    candidates=[match.pdf_result],
                    confidence="high",
                )
            )
            continue
        final_mapped.append(item)

    spreadsheet_issues_by_row: dict[int, list[SourceIssue]] = defaultdict(list)
    for issue in spreadsheet.issues:
        if issue.source_row is not None:
            spreadsheet_issues_by_row[issue.source_row].append(issue)
    for review in reviews:
        source_row = int(str(review["source_row"]))
        existing_issues = review.get("source_issues")
        serialized_issues = (
            list(existing_issues) if isinstance(existing_issues, list) else []
        )
        known_issue_keys = {
            (
                item.get("source_file"),
                item.get("source_row"),
                item.get("field"),
                item.get("code"),
            )
            for item in serialized_issues
            if isinstance(item, dict)
        }
        for issue in spreadsheet_issues_by_row.get(source_row, []):
            payload = _issue_payload(issue)
            key = (
                payload["source_file"],
                payload["source_row"],
                payload["field"],
                payload["code"],
            )
            if key not in known_issue_keys:
                serialized_issues.append(payload)
                known_issue_keys.add(key)
        review["source_issues"] = sorted(
            serialized_issues,
            key=lambda item: (
                str(item.get("code", "")) if isinstance(item, dict) else "",
                str(item.get("field", "")) if isinstance(item, dict) else "",
            ),
        )

    accepted_pdf_paths = {item[0].pdf_result.source_path for item in final_mapped}
    member_pdf_results = [
        result
        for result in pdf_results
        if result.source.kind in {PDFSourceKind.MEMBER, PDFSourceKind.UNKNOWN}
    ]
    unused_pdfs = [
        {
            "pdf_file": result.source_path.name,
            "pdf_ordinal": result.source.ordinal,
            "issues": [_issue_payload(issue) for issue in result.issues],
        }
        for result in member_pdf_results
        if result.source_path not in accepted_pdf_paths
    ]
    ignored_inputs = [
        {
            "file": result.source_path.name,
            "reason": "aggregate_pdf",
        }
        for result in pdf_results
        if result.source.kind == PDFSourceKind.AGGREGATE
    ]

    staged_photos_path = _prepare_output_directory(output_directory)
    photo_entries: list[dict[str, object]] = []
    photo_counts = Counter()
    accepted_matches: list[dict[str, object]] = []
    member_objects: list[dict[str, object]] = []
    address_objects: list[dict[str, object]] = []
    spreadsheet_warnings_by_row: dict[int, list[str]] = defaultdict(list)
    for issue in spreadsheet.issues:
        if issue.source_row is not None and issue.severity != "error":
            spreadsheet_warnings_by_row[issue.source_row].append(
                f"spreadsheet_issue:{issue.code}"
            )
    for match, pk, member_fields, address_fields, warnings in sorted(
        final_mapped, key=lambda item: item[0].spreadsheet.source_row
    ):
        member_objects.append(
            {"model": "members.member", "pk": pk, "fields": member_fields}
        )
        address_objects.append(
            {"model": "members.address", "fields": address_fields}
        )
        accepted_warnings = sorted(
            set(warnings)
            | set(spreadsheet_warnings_by_row[match.spreadsheet.source_row])
        )
        accepted_matches.append(
            {
                "source_row": match.spreadsheet.source_row,
                "source_ordinal": match.spreadsheet.ordinal,
                "member_pk": pk,
                "pdf_file": match.pdf_result.source_path.name,
                "confidence": "high",
                "rule": match.rule,
                "evidence": list(match.evidence),
                "warnings": accepted_warnings,
                "pdf_issues": [
                    _issue_payload(issue) for issue in match.pdf_result.issues
                ],
            }
        )

        photo_result = stage_pdf_photo(
            match.pdf_result.source_path,
            staged_photos_path,
            output_name=f"{pk}.jpg",
        )
        status_map = {
            PhotoStageStatus.STAGED: "ready",
            PhotoStageStatus.MISSING: "missing",
            PhotoStageStatus.AMBIGUOUS: "ambiguous",
            PhotoStageStatus.ERROR: "invalid",
        }
        photo_status = status_map[photo_result.status]
        photo_counts[photo_status] += 1
        photo_entry: dict[str, object] = {
            "member_pk": pk,
            "source_row": match.spreadsheet.source_row,
            "source_pdf": match.pdf_result.source_path.name,
            "status": photo_status,
            "photo_file": None,
            "sha256": None,
            "expected_identity": {
                "name": member_fields["name"],
                "birth_date": member_fields["birth_date"],
                "cpf": member_fields["cpf"],
            },
            "issues": [_issue_payload(issue) for issue in photo_result.issues],
        }
        if photo_result.manifest:
            manifest = photo_result.manifest
            photo_entry.update(
                {
                    "photo_file": manifest.staged_path.name,
                    "sha256": manifest.sha256,
                    "byte_size": manifest.byte_size,
                    "width": manifest.width,
                    "height": manifest.height,
                    "source_page": manifest.source_page,
                    "source_image_number": manifest.source_image_number,
                    "source_width": manifest.source_width,
                    "source_height": manifest.source_height,
                }
            )
        photo_entries.append(photo_entry)

    duplicate_photo_hashes = {
        digest
        for digest, count in Counter(
            entry["sha256"]
            for entry in photo_entries
            if entry["status"] == "ready" and entry["sha256"]
        ).items()
        if count > 1
    }
    if duplicate_photo_hashes:
        for entry in photo_entries:
            if entry["status"] != "ready" or entry["sha256"] not in duplicate_photo_hashes:
                continue
            entry["status"] = "ambiguous"
            entry["issues"] = [
                {
                    "source_file": entry["source_pdf"],
                    "source_row": entry["source_row"],
                    "field": "photo",
                    "code": "duplicate_photo_content",
                    "severity": "warning",
                    "message": "The same staged image belongs to multiple members.",
                    "raw_value": None,
                }
            ]
            photo_counts["ready"] -= 1
            photo_counts["ambiguous"] += 1

    fixture = member_objects + address_objects
    summary = {
        "spreadsheet_records": len(spreadsheet.records),
        "individual_pdfs": len(member_pdf_results),
        "aggregate_pdfs_ignored": len(ignored_inputs),
        "high_confidence_h1": sum(
            item["rule"] == "H1" for item in accepted_matches
        ),
        "high_confidence_h2": sum(
            item["rule"] == "H2" for item in accepted_matches
        ),
        "records_needing_review": len(reviews),
        "unmatched_spreadsheet_records": sum(
            _review_has_reason(item, "pdf_not_matched") for item in reviews
        ),
        "unused_individual_pdfs": len(unused_pdfs),
        "source_conflicts": sum(
            bool(item.get("conflicts")) for item in reviews
        ),
        "validation_errors": sum(
            bool(item.get("validation_errors")) for item in reviews
        ),
        "members_exported": len(member_objects),
        "addresses_exported": len(address_objects),
        "photos_ready": photo_counts["ready"],
        "photos_missing": photo_counts["missing"],
        "photos_ambiguous": photo_counts["ambiguous"],
        "photos_invalid": photo_counts["invalid"],
    }
    input_hashes = {
        "spreadsheet": {
            "file": spreadsheet_path.name,
            "sha256": _hash_file(spreadsheet_path),
        },
        "pdfs": [
            {"file": path.name, "sha256": _hash_file(path)} for path in pdf_paths
        ],
    }
    report = {
        "schema_version": 1,
        "snapshot_timestamp": timestamp,
        "accepted_matches": accepted_matches,
        "needs_review": sorted(
            reviews, key=lambda item: int(str(item["source_row"]))
        ),
        "unused_individual_pdfs": unused_pdfs,
        "ignored_inputs": ignored_inputs,
        "unmapped_source_data": _unmapped_source_summary(
            spreadsheet.records, pdf_results
        ),
        "input_hashes": input_hashes,
        "fixture_identity": {
            "member_pk_min": min(
                (item[1] for item in final_mapped), default=None
            ),
            "member_pk_max": max(
                (item[1] for item in final_mapped), default=None
            ),
            "member_pk_collision_check_required": True,
            "address_pk_strategy": "database_assigned",
        },
    }
    photo_manifest = {
        "schema_version": 1,
        "snapshot_timestamp": timestamp,
        "photos": photo_entries,
    }

    fixture_path = output_directory / "members_fixture.json"
    report_path = output_directory / "consolidation_report.json"
    summary_path = output_directory / "consolidation_summary.json"
    photo_manifest_path = output_directory / "photo_manifest.json"
    _write_json(fixture_path, fixture)
    _write_json(report_path, report)
    _write_json(summary_path, summary)
    _write_json(photo_manifest_path, photo_manifest)
    return ConsolidationResult(
        fixture_path=fixture_path,
        report_path=report_path,
        summary_path=summary_path,
        photo_manifest_path=photo_manifest_path,
        staged_photos_path=staged_photos_path,
        summary=summary,
    )
