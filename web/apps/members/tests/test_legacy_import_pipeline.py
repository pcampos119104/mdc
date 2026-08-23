"""Focused tests for deterministic legacy member consolidation artifacts."""

import hashlib
import json
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.members.legacy_import import pipeline
from apps.members.legacy_import.pipeline import (
    ConsolidationError,
    consolidate_legacy_members,
)
from apps.members.legacy_import.records import (
    PDFOccurrence,
    PDFReadResult,
    PDFRecord,
    PDFSource,
    PDFSourceKind,
    PhotoManifestEntry,
    PhotoStageResult,
    PhotoStageStatus,
    SourceIssue,
    SpreadsheetReadResult,
    SpreadsheetRecord,
)
from apps.members.models import Address, Member


SNAPSHOT_TIMESTAMP = "2026-01-02T03:04:05Z"
SYNTHETIC_PHOTO = b"synthetic staged photo bytes"


def _source_files(
    tmp_path: Path, pdf_names: tuple[str, ...] = ("001 Pessoa Exemplo.pdf",)
) -> tuple[Path, Path, tuple[Path, ...]]:
    """Create harmless files required for input discovery and hashing."""
    spreadsheet_path = tmp_path / "synthetic-members.xlsx"
    spreadsheet_path.write_bytes(b"synthetic workbook content")
    pdf_directory = tmp_path / "synthetic-pdfs"
    pdf_directory.mkdir()
    pdf_paths = tuple(pdf_directory / name for name in pdf_names)
    for pdf_path in pdf_paths:
        pdf_path.write_bytes(f"synthetic PDF: {pdf_path.name}".encode())
    return spreadsheet_path, pdf_directory, pdf_paths


def _spreadsheet_record(
    source_path: Path, **overrides: object
) -> SpreadsheetRecord:
    """Return one fully anonymized spreadsheet record."""
    values: dict[str, Any] = {
        "source_path": source_path,
        "source_row": 7,
        "ordinal": 1,
        "name_raw": "  Pessoa   Exemplo  ",
        "identification_raw": "SYNTHETIC-001",
        "person_type_raw": " Liderança ",
        "member_type_raw": "Som e Imagem",
        "birth_date_raw": "04/05/1990",
        "birth_date": date(1990, 5, 4),
        "street_raw": " Rua de Teste ",
        "street_number_raw": " 42 ",
        "complement_raw": " Sala 3 ",
        "district_raw": " Bairro Exemplo ",
        "city_raw": " Cidade Exemplo ",
        "state_raw": "São Paulo",
        "mobile_phone_raw": "+55 (11) 90000-0001",
        "home_phone_raw": "",
        "work_phone_raw": "",
        "contact_phone_raw": "",
        "email_raw": " pessoa.exemplo@example.invalid ",
        "group_participation_raw": "",
        "raw_fields": {},
    }
    values.update(overrides)
    return SpreadsheetRecord(**values)


def _pdf_result(
    source_path: Path,
    *,
    ordinal: int = 1,
    issues: tuple[SourceIssue, ...] = (),
    **overrides: object,
) -> PDFReadResult:
    """Return one parsed, anonymized individual PDF result."""
    source = PDFSource(
        source_path=source_path,
        kind=PDFSourceKind.MEMBER,
        ordinal=ordinal,
        name_raw="Pessoa Exemplo",
    )
    values: dict[str, Any] = {
        "source_path": source_path,
        "source": source,
        "registration_type_raw": "Liderança",
        "person_type_raw": "Som e Imagem",
        "name_raw": "Pessoa Exemplo",
        "cpf_raw": "529.982.247-25",
        "birth_date_raw": "4/5/1990",
        "sex_raw": "Feminino",
        "identification_raw": "SYNTHETIC-001",
        "nationality_raw": "",
        "birthplace_raw": " Cidade Natal de Teste ",
        "email_raw": "PESSOA.EXEMPLO@example.invalid",
        "contact_name_raw": "",
        "mobile_phone_raw": "+55 (11) 90000-0001",
        "home_phone_raw": "",
        "father_name_raw": " Pessoa Ascendente A ",
        "mother_name_raw": " Pessoa Ascendente B ",
        "spouse_name_raw": " Pessoa Cônjuge ",
        "marital_status_raw": "União estável",
        "postal_code_raw": "12345-678",
        "country_raw": "",
        "state_raw": "SP",
        "city_raw": "Cidade Exemplo",
        "street_raw": "Rua de Teste",
        "street_number_raw": "42",
        "complement_raw": "Sala 3",
        "district_raw": "Bairro Exemplo",
        "occurrences": (
            PDFOccurrence(
                ordinal=1,
                occurrence_type_raw="BATISMO",
                occurrence_date_raw="7/6/2010",
                occurrence_date=date(2010, 6, 7),
            ),
        ),
        "raw_fields": {},
    }
    values.update(overrides)
    record = PDFRecord(**values)
    return PDFReadResult(
        source_path=source_path,
        source=source,
        record=record,
        issues=issues,
    )


def _install_readers(
    monkeypatch: pytest.MonkeyPatch,
    spreadsheet_path: Path,
    records: tuple[SpreadsheetRecord, ...],
    pdf_results: tuple[PDFReadResult, ...],
    *,
    spreadsheet_issues: tuple[SourceIssue, ...] = (),
) -> None:
    """Replace source readers while retaining real artifact serialization."""
    spreadsheet_result = SpreadsheetReadResult(
        source_path=spreadsheet_path,
        headers=(),
        records=records,
        issues=spreadsheet_issues,
    )
    results_by_path = {result.source_path: result for result in pdf_results}
    monkeypatch.setattr(pipeline.shutil, "which", lambda executable: f"/bin/{executable}")
    monkeypatch.setattr(pipeline, "read_spreadsheet", lambda _path: spreadsheet_result)
    monkeypatch.setattr(pipeline, "read_pdf", lambda path: results_by_path[path])


def _stage_missing(
    source_path: Path, _output_directory: Path, *, output_name: str
) -> PhotoStageResult:
    """Return a deterministic no-photo decision."""
    assert output_name.endswith(".jpg")
    return PhotoStageResult(
        source_path=source_path,
        status=PhotoStageStatus.MISSING,
        manifest=None,
        issues=(),
    )


def _stage_ready(
    source_path: Path, output_directory: Path, *, output_name: str
) -> PhotoStageResult:
    """Stage deterministic bytes and return the production manifest contract."""
    staged_path = output_directory / output_name
    staged_path.write_bytes(SYNTHETIC_PHOTO)
    return PhotoStageResult(
        source_path=source_path,
        status=PhotoStageStatus.STAGED,
        manifest=PhotoManifestEntry(
            source_path=source_path,
            staged_path=staged_path,
            sha256=hashlib.sha256(SYNTHETIC_PHOTO).hexdigest(),
            byte_size=len(SYNTHETIC_PHOTO),
            width=320,
            height=240,
            source_page=1,
            source_image_number=0,
            source_width=640,
            source_height=480,
        ),
        issues=(),
    )


def _consolidate(
    spreadsheet_path: Path,
    pdf_directory: Path,
    output_directory: Path,
    *,
    pk_base: int = 700,
):
    """Run consolidation with an explicit reproducible timestamp."""
    return consolidate_legacy_members(
        spreadsheet_path=spreadsheet_path,
        pdf_directory=pdf_directory,
        output_directory=output_directory,
        pk_base=pk_base,
        snapshot_timestamp=SNAPSHOT_TIMESTAMP,
    )


def _read_json(path: Path):
    """Read one generated JSON artifact."""
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_bytes(directory: Path) -> dict[str, bytes]:
    """Snapshot every generated file by its output-relative name."""
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_h1_writes_normalized_fixture_and_ready_photo_without_database_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    django_db_blocker,
) -> None:
    """A corroborated H1 match should produce normalized, photo-safe artifacts."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    spreadsheet_record = _spreadsheet_record(spreadsheet_path)
    pdf_result = _pdf_result(pdf_path)
    _install_readers(
        monkeypatch, spreadsheet_path, (spreadsheet_record,), (pdf_result,)
    )
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_ready)

    with django_db_blocker.block():
        result = _consolidate(
            spreadsheet_path, pdf_directory, tmp_path / "artifacts"
        )

    fixture = _read_json(result.fixture_path)
    assert [item["model"] for item in fixture] == [
        "members.member",
        "members.address",
    ]
    assert fixture[0]["pk"] == 700
    assert "pk" not in fixture[1]
    member_fields = fixture[0]["fields"]
    assert member_fields["name"] == "Pessoa Exemplo"
    assert member_fields["photo"] == ""
    assert member_fields["registration_type"] == Member.RegistrationType.LEADERSHIP
    assert member_fields["classifications"] == [
        Member.Classification.SOUND_AND_MEDIA
    ]
    assert member_fields["cpf"] == "52998224725"
    assert member_fields["birth_date"] == "1990-05-04"
    assert member_fields["baptism_date"] == "2010-06-07"
    assert member_fields["sex"] == Member.Sex.FEMALE
    assert member_fields["phone"] == "5511900000001"
    assert member_fields["marital_status"] == Member.MaritalStatus.STABLE_UNION
    assert member_fields["created_at"] == SNAPSHOT_TIMESTAMP
    assert fixture[1]["fields"] == {
        "member": 700,
        "postal_code": "12345678",
        "state": "SP",
        "city": "Cidade Exemplo",
        "street": "Rua de Teste",
        "street_number": "42",
        "complement": "Sala 3",
        "district": "Bairro Exemplo",
    }

    report = _read_json(result.report_path)
    assert report["needs_review"] == []
    assert report["accepted_matches"] == [
        {
            "source_row": 7,
            "source_ordinal": 1,
            "member_pk": 700,
            "pdf_file": pdf_path.name,
            "confidence": "high",
            "rule": "H1",
            "evidence": ["birth_date", "email", "mobile_phone", "address"],
            "warnings": [],
            "pdf_issues": [],
        }
    ]
    assert result.summary["high_confidence_h1"] == 1
    assert result.summary["members_exported"] == 1
    assert result.summary["addresses_exported"] == 1
    assert result.summary["photos_ready"] == 1

    manifest = _read_json(result.photo_manifest_path)
    assert manifest["schema_version"] == 1
    assert manifest["snapshot_timestamp"] == SNAPSHOT_TIMESTAMP
    assert manifest["photos"] == [
        {
            "member_pk": 700,
            "source_row": 7,
            "source_pdf": pdf_path.name,
            "status": "ready",
            "photo_file": "700.jpg",
            "sha256": hashlib.sha256(SYNTHETIC_PHOTO).hexdigest(),
            "expected_identity": {
                "name": "Pessoa Exemplo",
                "birth_date": "1990-05-04",
                "cpf": "52998224725",
            },
            "issues": [],
            "byte_size": len(SYNTHETIC_PHOTO),
            "width": 320,
            "height": 240,
            "source_page": 1,
            "source_image_number": 0,
            "source_width": 640,
            "source_height": 480,
        }
    ]
    assert (result.staged_photos_path / "700.jpg").read_bytes() == SYNTHETIC_PHOTO


def test_contradictory_identification_blocks_h1_and_preserves_spreadsheet_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Populated identification disagreement should require manual review."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    record = _spreadsheet_record(
        spreadsheet_path, identification_raw="SYNTHETIC-SHEET-001"
    )
    pdf_result = _pdf_result(
        pdf_path, identification_raw="SYNTHETIC-PDF-999"
    )
    spreadsheet_warning = SourceIssue(
        source_path=spreadsheet_path,
        source_row=record.source_row,
        field="identification",
        code="synthetic_format_warning",
        message="Synthetic nonblocking spreadsheet warning.",
        severity="warning",
        raw_value="SYNTHETIC-SHEET-001",
    )
    _install_readers(
        monkeypatch,
        spreadsheet_path,
        (record,),
        (pdf_result,),
        spreadsheet_issues=(spreadsheet_warning,),
    )
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_missing)

    result = _consolidate(spreadsheet_path, pdf_directory, tmp_path / "artifacts")

    report = _read_json(result.report_path)
    assert _read_json(result.fixture_path) == []
    assert report["accepted_matches"] == []
    assert result.summary["high_confidence_h1"] == 0
    assert report["needs_review"][0]["reason_codes"] == ["source_conflict"]
    assert report["needs_review"][0]["conflicts"] == [
        {
            "field": "identification",
            "spreadsheet_value": "SYNTHETIC-SHEET-001",
            "pdf_value": "SYNTHETIC-PDF-999",
        }
    ]
    assert report["needs_review"][0]["source_issues"] == [
        {
            "source_file": spreadsheet_path.name,
            "source_row": 7,
            "field": "identification",
            "code": "synthetic_format_warning",
            "severity": "warning",
            "message": "Synthetic nonblocking spreadsheet warning.",
            "raw_value": "SYNTHETIC-SHEET-001",
        }
    ]


def test_whitespace_only_spreadsheet_values_fall_back_to_pdf_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Whitespace-only optional fields should not mask populated PDF values."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    record = _spreadsheet_record(
        spreadsheet_path,
        birth_date_raw="   ",
        birth_date=None,
        email_raw=" \t ",
        state_raw="   ",
        city_raw="\n",
        street_raw="   ",
        street_number_raw="\t",
        complement_raw="   ",
        district_raw="\n",
    )
    pdf_result = _pdf_result(
        pdf_path,
        email_raw="fallback@example.invalid",
        state_raw="Rio de Janeiro",
        city_raw="Cidade PDF",
        street_raw="Rua PDF",
        street_number_raw="88",
        complement_raw="Bloco PDF",
        district_raw="Bairro PDF",
    )
    _install_readers(monkeypatch, spreadsheet_path, (record,), (pdf_result,))
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_missing)

    result = _consolidate(spreadsheet_path, pdf_directory, tmp_path / "artifacts")

    fixture = _read_json(result.fixture_path)
    member_fields = fixture[0]["fields"]
    address_fields = fixture[1]["fields"]
    assert member_fields["birth_date"] == "1990-05-04"
    assert member_fields["email"] == "fallback@example.invalid"
    assert address_fields == {
        "member": 700,
        "postal_code": "12345678",
        "state": "RJ",
        "city": "Cidade PDF",
        "street": "Rua PDF",
        "street_number": "88",
        "complement": "Bloco PDF",
        "district": "Bairro PDF",
    }
    assert result.summary["members_exported"] == 1


@pytest.mark.parametrize(
    ("phone_field", "raw_phone", "expected_phone"),
    (
        ("work_phone_raw", "(11) 90000-0002", "11900000002"),
        ("contact_phone_raw", "(11) 90000-0003", "11900000003"),
    ),
)
def test_work_or_contact_phone_can_be_selected_as_last_resort(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    phone_field: str,
    raw_phone: str,
    expected_phone: str,
) -> None:
    """Each spreadsheet-only phone source should be usable as a fallback."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    record_overrides = {
        "mobile_phone_raw": "",
        "home_phone_raw": "",
        "work_phone_raw": "",
        "contact_phone_raw": "",
        phone_field: raw_phone,
    }
    record = _spreadsheet_record(spreadsheet_path, **record_overrides)
    pdf_result = _pdf_result(pdf_path, mobile_phone_raw="", home_phone_raw="")
    _install_readers(monkeypatch, spreadsheet_path, (record,), (pdf_result,))
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_missing)

    result = _consolidate(spreadsheet_path, pdf_directory, tmp_path / "artifacts")

    fixture = _read_json(result.fixture_path)
    report = _read_json(result.report_path)
    assert fixture[0]["fields"]["phone"] == expected_phone
    assert report["accepted_matches"][0]["warnings"] == []
    assert result.summary["members_exported"] == 1


def test_additional_work_and_contact_phones_are_warned_and_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Only the first fallback phone should map while both source fields are reported."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    record = _spreadsheet_record(
        spreadsheet_path,
        mobile_phone_raw="",
        home_phone_raw="",
        work_phone_raw="(11) 90000-0002",
        contact_phone_raw="(11) 90000-0003",
    )
    pdf_result = _pdf_result(pdf_path, mobile_phone_raw="", home_phone_raw="")
    _install_readers(monkeypatch, spreadsheet_path, (record,), (pdf_result,))
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_missing)

    result = _consolidate(spreadsheet_path, pdf_directory, tmp_path / "artifacts")

    fixture = _read_json(result.fixture_path)
    report = _read_json(result.report_path)
    assert fixture[0]["fields"]["phone"] == "11900000002"
    assert report["accepted_matches"][0]["warnings"] == [
        "additional_phone_not_imported"
    ]
    assert report["unmapped_source_data"]["work_phone_populated"] == 1
    assert report["unmapped_source_data"]["contact_phone_populated"] == 1


def test_duplicate_staged_photo_hashes_become_ambiguous(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Identical staged content should never remain ready for two members."""
    spreadsheet_path, pdf_directory, pdf_paths = _source_files(
        tmp_path,
        ("001 Pessoa Foto A.pdf", "002 Pessoa Foto B.pdf"),
    )
    records = (
        _spreadsheet_record(
            spreadsheet_path,
            source_row=7,
            ordinal=1,
            name_raw="Pessoa Foto A",
            identification_raw="SYNTHETIC-PHOTO-A",
            email_raw="foto.a@example.invalid",
        ),
        _spreadsheet_record(
            spreadsheet_path,
            source_row=8,
            ordinal=2,
            name_raw="Pessoa Foto B",
            identification_raw="SYNTHETIC-PHOTO-B",
            email_raw="foto.b@example.invalid",
        ),
    )
    pdf_results = (
        _pdf_result(
            pdf_paths[0],
            ordinal=1,
            name_raw="Pessoa Foto A",
            identification_raw="SYNTHETIC-PHOTO-A",
            email_raw="foto.a@example.invalid",
            cpf_raw="",
        ),
        _pdf_result(
            pdf_paths[1],
            ordinal=2,
            name_raw="Pessoa Foto B",
            identification_raw="SYNTHETIC-PHOTO-B",
            email_raw="foto.b@example.invalid",
            cpf_raw="",
        ),
    )
    _install_readers(monkeypatch, spreadsheet_path, records, pdf_results)
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_ready)

    result = _consolidate(spreadsheet_path, pdf_directory, tmp_path / "artifacts")

    fixture = _read_json(result.fixture_path)
    photos = _read_json(result.photo_manifest_path)["photos"]
    assert len(fixture) == 4
    assert all("pk" not in item for item in fixture if item["model"] == "members.address")
    assert [photo["status"] for photo in photos] == ["ambiguous", "ambiguous"]
    assert {photo["sha256"] for photo in photos} == {
        hashlib.sha256(SYNTHETIC_PHOTO).hexdigest()
    }
    assert [photo["issues"][0]["code"] for photo in photos] == [
        "duplicate_photo_content",
        "duplicate_photo_content",
    ]
    assert result.summary["photos_ready"] == 0
    assert result.summary["photos_ambiguous"] == 2


def test_unmapped_classification_warns_without_blocking_export(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An evolving legacy member type should remain exportable with a warning."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    record = _spreadsheet_record(
        spreadsheet_path, member_type_raw="Equipe Experimental"
    )
    pdf_result = _pdf_result(pdf_path, person_type_raw="Equipe Experimental")
    _install_readers(monkeypatch, spreadsheet_path, (record,), (pdf_result,))
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_missing)

    result = _consolidate(spreadsheet_path, pdf_directory, tmp_path / "artifacts")

    fixture = _read_json(result.fixture_path)
    report = _read_json(result.report_path)
    assert fixture[0]["fields"]["classifications"] == []
    assert report["accepted_matches"][0]["warnings"] == ["unmapped_member_type"]
    assert report["needs_review"] == []
    assert report["unmapped_source_data"]["member_type_values"] == {
        "Equipe Experimental": 1
    }
    assert result.summary["members_exported"] == 1


def test_conflict_and_parser_issue_go_to_review_and_leave_deterministic_pk_gap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unsafe rows should be excluded while later ordinals retain stable PKs."""
    spreadsheet_path, pdf_directory, pdf_paths = _source_files(
        tmp_path,
        (
            "001 Pessoa Conflito.pdf",
            "002 Pessoa Parser.pdf",
            "003 Pessoa Aceita.pdf",
        ),
    )
    records = (
        _spreadsheet_record(
            spreadsheet_path,
            source_row=7,
            ordinal=1,
            name_raw="Pessoa Conflito",
            email_raw="conflito@example.invalid",
        ),
        _spreadsheet_record(
            spreadsheet_path,
            source_row=8,
            ordinal=2,
            name_raw="Pessoa Parser",
            email_raw="parser@example.invalid",
        ),
        _spreadsheet_record(
            spreadsheet_path,
            source_row=9,
            ordinal=3,
            name_raw="Pessoa Aceita",
            email_raw="aceita@example.invalid",
        ),
    )
    parser_issue = SourceIssue(
        source_path=pdf_paths[1],
        code="missing_label",
        message="Synthetic parser warning.",
        severity="warning",
        field="name",
    )
    pdf_results = (
        _pdf_result(
            pdf_paths[0],
            ordinal=1,
            name_raw="Pessoa Conflito",
            email_raw="divergente@example.invalid",
        ),
        _pdf_result(
            pdf_paths[1],
            ordinal=2,
            issues=(parser_issue,),
            name_raw="Pessoa Parser",
            email_raw="parser@example.invalid",
        ),
        _pdf_result(
            pdf_paths[2],
            ordinal=3,
            name_raw="Pessoa Aceita",
            email_raw="aceita@example.invalid",
        ),
    )
    _install_readers(monkeypatch, spreadsheet_path, records, pdf_results)
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_missing)

    result = _consolidate(
        spreadsheet_path, pdf_directory, tmp_path / "artifacts", pk_base=100
    )

    fixture = _read_json(result.fixture_path)
    report = _read_json(result.report_path)
    assert fixture[0]["pk"] == 102
    assert "pk" not in fixture[1]
    assert report["accepted_matches"][0]["source_ordinal"] == 3
    reviews_by_ordinal = {
        review["source_ordinal"]: review for review in report["needs_review"]
    }
    assert "source_conflict" in reviews_by_ordinal[1]["reason_codes"]
    assert reviews_by_ordinal[1]["conflicts"] == [
        {
            "field": "email",
            "spreadsheet_value": "conflito@example.invalid",
            "pdf_value": "divergente@example.invalid",
        }
    ]
    assert reviews_by_ordinal[2]["reason_codes"] == ["pdf_parse_issue"]
    assert reviews_by_ordinal[2]["source_issues"][0]["code"] == "missing_label"
    assert result.summary["records_needing_review"] == 2
    assert result.summary["source_conflicts"] == 1
    assert result.summary["members_exported"] == 1


def test_nonempty_output_directory_is_refused_without_overwriting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Consolidation should not mix artifacts with existing output content."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    _install_readers(
        monkeypatch,
        spreadsheet_path,
        (_spreadsheet_record(spreadsheet_path),),
        (_pdf_result(pdf_path),),
    )
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_missing)
    output_directory = tmp_path / "artifacts"
    output_directory.mkdir()
    sentinel = output_directory / "keep.txt"
    sentinel.write_text("existing content", encoding="utf-8")

    with pytest.raises(ConsolidationError, match="Output directory must be empty"):
        _consolidate(spreadsheet_path, pdf_directory, output_directory)

    assert sentinel.read_text(encoding="utf-8") == "existing content"
    assert list(output_directory.iterdir()) == [sentinel]


def test_pk_range_beyond_signed_big_auto_field_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Source ordinals may not push deterministic member PKs beyond bigint."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(
        tmp_path, ("002 Pessoa Limite.pdf",)
    )
    record = _spreadsheet_record(
        spreadsheet_path,
        source_row=8,
        ordinal=2,
        name_raw="Pessoa Limite",
        identification_raw="SYNTHETIC-LIMIT-002",
    )
    pdf_result = _pdf_result(
        pdf_path,
        ordinal=2,
        name_raw="Pessoa Limite",
        identification_raw="SYNTHETIC-LIMIT-002",
    )
    _install_readers(monkeypatch, spreadsheet_path, (record,), (pdf_result,))

    with pytest.raises(
        ConsolidationError, match="PK range exceeds the signed BigAutoField limit"
    ):
        _consolidate(
            spreadsheet_path,
            pdf_directory,
            tmp_path / "artifacts",
            pk_base=2**63 - 1,
        )

    assert not (tmp_path / "artifacts").exists()


def test_same_logical_input_produces_byte_identical_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Repeated consolidation should serialize every output deterministically."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    _install_readers(
        monkeypatch,
        spreadsheet_path,
        (_spreadsheet_record(spreadsheet_path),),
        (_pdf_result(pdf_path),),
    )
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_ready)
    first_output = tmp_path / "first-output"
    second_output = tmp_path / "second-output"

    _consolidate(spreadsheet_path, pdf_directory, first_output, pk_base=1200)
    _consolidate(spreadsheet_path, pdf_directory, second_output, pk_base=1200)

    assert _artifact_bytes(first_output) == _artifact_bytes(second_output)


def test_management_command_requires_pk_base_and_prints_only_aggregate_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The command should require deterministic IDs and avoid printing identities."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    output_directory = tmp_path / "artifacts"

    with pytest.raises(CommandError, match="--pk-base"):
        call_command(
            "consolidate_legacy_members",
            "--spreadsheet",
            str(spreadsheet_path),
            "--pdf-dir",
            str(pdf_directory),
            "--output-dir",
            str(output_directory),
        )

    _install_readers(
        monkeypatch,
        spreadsheet_path,
        (_spreadsheet_record(spreadsheet_path),),
        (_pdf_result(pdf_path),),
    )
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_missing)
    stdout = StringIO()

    call_command(
        "consolidate_legacy_members",
        "--spreadsheet",
        str(spreadsheet_path),
        "--pdf-dir",
        str(pdf_directory),
        "--output-dir",
        str(output_directory),
        "--pk-base",
        "300",
        "--snapshot-timestamp",
        SNAPSHOT_TIMESTAMP,
        stdout=stdout,
    )

    command_output = stdout.getvalue()
    assert "members_exported=1" in command_output
    assert f"Artifacts: {output_directory}" in command_output
    assert "Pessoa Exemplo" not in command_output
    assert _read_json(output_directory / "members_fixture.json")[0]["pk"] == 300


@pytest.mark.django_db(transaction=True)
def test_generated_fixture_loaddata_compatibility_and_consolidation_does_not_write_db(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The generated member/address fixture should load only when explicitly asked."""
    spreadsheet_path, pdf_directory, (pdf_path,) = _source_files(tmp_path)
    _install_readers(
        monkeypatch,
        spreadsheet_path,
        (_spreadsheet_record(spreadsheet_path),),
        (_pdf_result(pdf_path),),
    )
    monkeypatch.setattr(pipeline, "stage_pdf_photo", _stage_missing)
    assert Member.all_objects.count() == 0
    assert Address._default_manager.count() == 0

    result = _consolidate(
        spreadsheet_path, pdf_directory, tmp_path / "artifacts", pk_base=9000
    )

    assert Member.all_objects.count() == 0
    assert Address._default_manager.count() == 0
    call_command("loaddata", str(result.fixture_path), verbosity=0)

    member = Member.all_objects.get(pk=9000)
    address = Address._default_manager.get(member=member)
    assert member.name == "Pessoa Exemplo"
    assert member.birth_date == date(1990, 5, 4)
    assert member.baptism_date == date(2010, 6, 7)
    assert member.classifications == [Member.Classification.SOUND_AND_MEDIA]
    assert not member.photo
    assert address.member == member
    assert address.postal_code == "12345678"
    member.full_clean()
    address.full_clean()
