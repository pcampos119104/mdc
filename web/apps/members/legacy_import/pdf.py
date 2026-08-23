"""Read legacy member PDFs and conservatively stage their embedded photos."""

import hashlib
import io
import os
import re
import subprocess
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageOps, UnidentifiedImageError

from .normalization import comparison_key, parse_brazilian_date
from .records import (
    PDFOccurrence,
    PDFReadResult,
    PDFRecord,
    PDFSource,
    PDFSourceKind,
    PhotoManifestEntry,
    PhotoStageResult,
    PhotoStageStatus,
    SourceIssue,
)


PDFTOTEXT_TIMEOUT_SECONDS = 30
PDFIMAGES_TIMEOUT_SECONDS = 30
PDFTOHTML_TIMEOUT_SECONDS = 30
PHOTO_MIN_SOURCE_DIMENSION = 256
PHOTO_MAX_SOURCE_DIMENSION = 10_000
PHOTO_MAX_SOURCE_PIXELS = 50_000_000
STAGED_PHOTO_MAX_DIMENSION = 512
STAGED_PHOTO_JPEG_QUALITY = 85
FIELD_BASELINE_TOLERANCE = 2.0
PROFILE_LAYOUT_LEFT_RANGE = (40.0, 80.0)
PROFILE_LAYOUT_TOP_RANGE = (480.0, 530.0)
PROFILE_LAYOUT_SIZE_RANGE = (80.0, 140.0)

_MEMBER_FILENAME = re.compile(
    r"^(?P<ordinal>\d{3})\s+(?P<name>.+)\.pdf$", re.IGNORECASE
)
_AGGREGATE_NAME = "listagem de pessoas"
_PDF_FIELDS = (
    ("registration_type_raw", "Tipo Cadastro"),
    ("person_type_raw", "Tipo de pessoa"),
    ("name_raw", "Nome"),
    ("cpf_raw", "CPF"),
    ("birth_date_raw", "Nascimento"),
    ("sex_raw", "Sexo"),
    ("identification_raw", "Identificação"),
    ("nationality_raw", "Nacionalidade"),
    ("birthplace_raw", "Naturalidade - Cidade"),
    ("email_raw", "Email"),
    ("contact_name_raw", "Nome Contato"),
    ("mobile_phone_raw", "Celular Principal SMS"),
    ("home_phone_raw", "Telefone Fixo"),
    ("father_name_raw", "Pai"),
    ("mother_name_raw", "Mãe"),
    ("spouse_name_raw", "Esposo(a)"),
    ("marital_status_raw", "Estado Civil"),
    ("postal_code_raw", "CEP"),
    ("country_raw", "País"),
    ("state_raw", "Estado / Província"),
    ("city_raw", "Cidade"),
    ("street_raw", "Logradouro"),
    ("street_number_raw", "Número"),
    ("complement_raw", "Complemento"),
    ("district_raw", "Bairro"),
)
_IGNORED_LINE_KEYS = frozenset(
    comparison_key(value)
    for value in (
        "COMUNIDADE CRISTÃ EM PARQUE BRISTOL",
        "Dados Pessoais",
        "Contatos",
        "Familiares",
        "Endereço Residencial",
        "Principais Ocorrências",
        "Local da Ocorrência",
        "Responsável pela Ocorrência",
        "Possui WhatsApp (Celular)",
        "+ Adicionar",
        "Funções",
        "Funções em Grupos",
        "Funções em Ministérios",
    )
)
_OCCURRENCE_HEADING_KEY = comparison_key("Principais Ocorrências")
_OCCURRENCE_STOP_KEYS = frozenset(
    {
        comparison_key("Local da Ocorrência"),
        comparison_key("Responsável pela Ocorrência"),
        comparison_key("Funções"),
        comparison_key("Funções em Grupos"),
        comparison_key("Funções em Ministérios"),
    }
)


@dataclass(frozen=True, slots=True)
class _GeometryLine:
    """Store one Poppler XHTML text line and its page geometry."""

    index: int
    page: int
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    text: str


@dataclass(frozen=True, slots=True)
class _ImageCandidate:
    """Store relevant columns from one ``pdfimages -list`` row."""

    page: int
    number: int
    image_type: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class _LayoutImage:
    """Store displayed image geometry from Poppler layout XML."""

    left: float
    top: float
    width: float
    height: float


class _UnsafePhotoError(ValueError):
    """Report an image whose declared dimensions are unsafe for staging."""


def parse_pdf_filename(path: str | Path) -> PDFSource:
    """Parse a numbered member filename or classify the aggregate PDF."""
    source_path = Path(path)
    if (
        source_path.suffix.casefold() == ".pdf"
        and comparison_key(source_path.stem) == _AGGREGATE_NAME
    ):
        return PDFSource(
            source_path=source_path,
            kind=PDFSourceKind.AGGREGATE,
            ordinal=None,
            name_raw=source_path.stem,
        )

    match = _MEMBER_FILENAME.fullmatch(source_path.name)
    if match:
        return PDFSource(
            source_path=source_path,
            kind=PDFSourceKind.MEMBER,
            ordinal=int(match.group("ordinal")),
            name_raw=match.group("name"),
        )
    return PDFSource(
        source_path=source_path,
        kind=PDFSourceKind.UNKNOWN,
        ordinal=None,
        name_raw=source_path.stem,
    )


def classify_pdf_source(path: str | Path) -> PDFSourceKind:
    """Return the source kind encoded by a legacy PDF filename."""
    return parse_pdf_filename(path).kind


def _local_name(element: ElementTree.Element) -> str:
    """Return an XML tag name without its namespace."""
    return element.tag.rsplit("}", 1)[-1]


def _geometry_lines(xhtml: str) -> tuple[_GeometryLine, ...]:
    """Parse Poppler bbox XHTML into geometry-sorted text lines."""
    try:
        root = ElementTree.fromstring(xhtml)
    except ElementTree.ParseError as exc:
        raise ValueError("pdftotext returned malformed bbox XHTML.") from exc

    lines: list[_GeometryLine] = []
    page_number = 0
    pages = (element for element in root.iter() if _local_name(element) == "page")
    for page in pages:
        page_number += 1
        page_lines = (
            element for element in page.iter() if _local_name(element) == "line"
        )
        for line in page_lines:
            words = [
                word.text or ""
                for word in line.iter()
                if _local_name(word) == "word"
            ]
            text = " ".join(word for word in words if word)
            if not text:
                continue
            try:
                lines.append(
                    _GeometryLine(
                        index=len(lines),
                        page=page_number,
                        x_min=float(line.get("xMin", "")),
                        y_min=float(line.get("yMin", "")),
                        x_max=float(line.get("xMax", "")),
                        y_max=float(line.get("yMax", "")),
                        text=text,
                    )
                )
            except ValueError as exc:
                raise ValueError("pdftotext returned invalid line geometry.") from exc
    if not lines:
        raise ValueError("pdftotext returned no positioned text lines.")
    return tuple(
        sorted(lines, key=lambda item: (item.page, item.y_min, item.x_min))
    )


def _extract_fields(
    path: Path, lines: tuple[_GeometryLine, ...]
) -> tuple[dict[str, str], dict[str, str], list[SourceIssue], set[int]]:
    """Extract known labels using their nearby value geometry."""
    issues: list[SourceIssue] = []
    label_keys = {comparison_key(label) for _attribute, label in _PDF_FIELDS}
    matches_by_key = {
        key: [line for line in lines if comparison_key(line.text) == key]
        for key in label_keys
    }
    excluded_indexes = {
        line.index
        for line in lines
        if comparison_key(line.text) in label_keys | _IGNORED_LINE_KEYS
    }
    label_starts = sorted(
        {
            line.x_min
            for matches in matches_by_key.values()
            for line in matches
        }
    )

    attributes: dict[str, str] = {}
    raw_fields: dict[str, str] = {}
    for attribute, label in _PDF_FIELDS:
        matches = matches_by_key[comparison_key(label)]
        if len(matches) != 1:
            code = "missing_label" if not matches else "ambiguous_label"
            issues.append(
                SourceIssue(
                    source_path=path,
                    field=label,
                    code=code,
                    message=(
                        f"PDF label {label!r} was not found."
                        if not matches
                        else f"PDF label {label!r} appears more than once."
                    ),
                    severity="warning" if not matches else "error",
                )
            )
            attributes[attribute] = ""
            raw_fields[label] = ""
            continue

        label_line = matches[0]
        next_starts = [
            start for start in label_starts if start > label_line.x_min + 20
        ]
        x_max = next_starts[0] - 4 if next_starts else float("inf")
        candidates = [
            line
            for line in lines
            if line.page == label_line.page
            and line.index not in excluded_indexes
            and label_line.y_min + 8 < line.y_min <= label_line.y_min + 42
            and line.x_min >= label_line.x_min - 4
            and line.x_min < x_max
        ]
        baseline_groups: list[list[_GeometryLine]] = []
        for candidate in sorted(candidates, key=lambda line: (line.y_min, line.x_min)):
            if (
                not baseline_groups
                or candidate.y_min - baseline_groups[-1][0].y_min
                > FIELD_BASELINE_TOLERANCE
            ):
                baseline_groups.append([candidate])
            else:
                baseline_groups[-1].append(candidate)

        if len(baseline_groups) > 1:
            issues.append(
                SourceIssue(
                    source_path=path,
                    field=label,
                    raw_value="\n".join(line.text for line in candidates),
                    code="ambiguous_field_value",
                    message=(
                        f"PDF field {label!r} has values on multiple baselines."
                    ),
                )
            )
            attributes[attribute] = ""
            raw_fields[label] = ""
            continue

        value = (
            " ".join(
                line.text
                for line in sorted(baseline_groups[0], key=lambda line: line.x_min)
            )
            if baseline_groups
            else ""
        )
        attributes[attribute] = value
        raw_fields[label] = value
    return attributes, raw_fields, issues, excluded_indexes


def _extract_occurrences(
    path: Path,
    lines: tuple[_GeometryLine, ...],
    excluded_indexes: set[int],
) -> tuple[tuple[PDFOccurrence, ...], str, list[SourceIssue]]:
    """Extract repeatable occurrence type/date pairs without inferring bad dates."""
    headings = [
        line for line in lines if comparison_key(line.text) == _OCCURRENCE_HEADING_KEY
    ]
    if not headings:
        return (), "", []

    issues: list[SourceIssue] = []
    occurrences: list[PDFOccurrence] = []
    all_raw_lines: list[str] = []
    for heading in headings:
        stops = [
            line.y_min
            for line in lines
            if line.page == heading.page
            and line.y_min > heading.y_min
            and comparison_key(line.text) in _OCCURRENCE_STOP_KEYS
        ]
        stop_y = min(stops) if stops else float("inf")
        occurrence_lines = [
            line
            for line in lines
            if line.page == heading.page
            and line.index not in excluded_indexes
            and line.y_min > heading.y_max
            and line.y_min < stop_y
        ]
        all_raw_lines.extend(line.text for line in occurrence_lines)
        dates = {
            line.index: parsed
            for line in occurrence_lines
            if (parsed := parse_brazilian_date(line.text)) is not None
        }
        used_types: set[int] = set()
        unmatched_dates: list[_GeometryLine] = []
        for date_line in (line for line in occurrence_lines if line.index in dates):
            type_candidates = [
                line
                for line in occurrence_lines
                if line.index not in dates
                and line.index not in used_types
                and 0 <= date_line.y_min - line.y_min <= 35
                and abs(date_line.x_min - line.x_min) <= 80
            ]
            if not type_candidates:
                unmatched_dates.append(date_line)
                continue

            ranked = sorted(
                type_candidates,
                key=lambda line: (
                    abs(date_line.x_min - line.x_min),
                    date_line.y_min - line.y_min,
                ),
            )
            best_type = ranked[0]
            best_rank = (
                abs(date_line.x_min - best_type.x_min),
                date_line.y_min - best_type.y_min,
            )
            if len(ranked) > 1 and (
                abs(date_line.x_min - ranked[1].x_min),
                date_line.y_min - ranked[1].y_min,
            ) == best_rank:
                unmatched_dates.append(date_line)
                continue

            used_types.add(best_type.index)
            occurrences.append(
                PDFOccurrence(
                    ordinal=len(occurrences) + 1,
                    occurrence_type_raw=best_type.text,
                    occurrence_date_raw=date_line.text,
                    occurrence_date=dates[date_line.index],
                )
            )

        unpaired_lines = [
            line.text
            for line in occurrence_lines
            if line.index not in dates and line.index not in used_types
        ]
        if unpaired_lines:
            issues.append(
                SourceIssue(
                    source_path=path,
                    field="Principais Ocorrências",
                    raw_value="\n".join(unpaired_lines),
                    code="unpaired_occurrence",
                    message="Occurrence text could not be paired with a nearby date.",
                )
            )
        if unmatched_dates:
            issues.append(
                SourceIssue(
                    source_path=path,
                    field="Principais Ocorrências",
                    raw_value="\n".join(line.text for line in unmatched_dates),
                    code="occurrence_without_type",
                    message="Occurrence date has no unambiguous nearby type.",
                )
            )
    return tuple(occurrences), "\n".join(all_raw_lines), issues


def read_pdf(path: str | Path) -> PDFReadResult:
    """Read one numbered member PDF through Poppler bbox XHTML output."""
    source_path = Path(path)
    source = parse_pdf_filename(source_path)
    issues: list[SourceIssue] = []
    if source_path.suffix.casefold() != ".pdf":
        issues.append(
            SourceIssue(
                source_path=source_path,
                code="unsupported_pdf_source",
                message="Expected a source file with the .pdf extension.",
            )
        )
        return PDFReadResult(source_path, source, None, tuple(issues))
    if not source_path.is_file():
        issues.append(
            SourceIssue(
                source_path=source_path,
                code="missing_pdf",
                message="Source PDF does not exist.",
            )
        )
        return PDFReadResult(source_path, source, None, tuple(issues))
    if source.kind == PDFSourceKind.AGGREGATE:
        issues.append(
            SourceIssue(
                source_path=source_path,
                code="aggregate_pdf",
                message="Aggregate person listing was classified and not parsed as a member.",
                severity="info",
            )
        )
        return PDFReadResult(source_path, source, None, tuple(issues))
    if source.kind == PDFSourceKind.UNKNOWN:
        issues.append(
            SourceIssue(
                source_path=source_path,
                code="unrecognized_pdf_filename",
                message="PDF filename does not follow the 'NNN name.pdf' convention.",
                severity="warning",
            )
        )

    try:
        completed = subprocess.run(
            ["pdftotext", "-bbox-layout", str(source_path), "-"],
            capture_output=True,
            check=False,
            text=True,
            timeout=PDFTOTEXT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        issues.append(
            SourceIssue(
                source_path=source_path,
                code="pdftotext_timeout",
                message=(
                    "pdftotext exceeded the "
                    f"{PDFTOTEXT_TIMEOUT_SECONDS}-second timeout."
                ),
            )
        )
        return PDFReadResult(source_path, source, None, tuple(issues))
    except OSError as exc:
        issues.append(
            SourceIssue(
                source_path=source_path,
                code="pdftotext_unavailable",
                message=f"Poppler pdftotext could not be executed: {exc}",
            )
        )
        return PDFReadResult(source_path, source, None, tuple(issues))
    if completed.returncode:
        issues.append(
            SourceIssue(
                source_path=source_path,
                code="pdftotext_failed",
                message=f"pdftotext failed: {completed.stderr.strip() or 'unknown error'}",
            )
        )
        return PDFReadResult(source_path, source, None, tuple(issues))

    try:
        lines = _geometry_lines(completed.stdout)
    except ValueError as exc:
        issues.append(
            SourceIssue(
                source_path=source_path,
                code="invalid_pdf_geometry",
                message=str(exc),
            )
        )
        return PDFReadResult(source_path, source, None, tuple(issues))

    attributes, raw_fields, field_issues, excluded_indexes = _extract_fields(
        source_path, lines
    )
    issues.extend(field_issues)
    occurrences, occurrences_raw, occurrence_issues = _extract_occurrences(
        source_path, lines, excluded_indexes
    )
    raw_fields["Principais Ocorrências"] = occurrences_raw
    issues.extend(occurrence_issues)

    if not attributes["name_raw"]:
        issues.append(
            SourceIssue(
                source_path=source_path,
                field="Nome",
                code="missing_name",
                message="PDF does not contain an unambiguous member name.",
            )
        )
    elif source.kind == PDFSourceKind.MEMBER and comparison_key(
        source.name_raw
    ) != comparison_key(attributes["name_raw"]):
        issues.append(
            SourceIssue(
                source_path=source_path,
                field="Nome",
                raw_value=attributes["name_raw"],
                code="filename_name_mismatch",
                message="PDF member name does not match its filename.",
                severity="warning",
            )
        )

    record = PDFRecord(
        source_path=source_path,
        source=source,
        occurrences=occurrences,
        raw_fields=raw_fields,
        **attributes,
    )
    return PDFReadResult(source_path, source, record, tuple(issues))


def _parse_image_candidates(output: str) -> tuple[_ImageCandidate, ...]:
    """Parse stable leading columns from ``pdfimages -list`` output."""
    candidates: list[_ImageCandidate] = []
    for line in output.splitlines():
        columns = line.split()
        if (
            len(columns) < 5
            or not columns[0].isdigit()
            or not columns[1].isdigit()
        ):
            continue
        try:
            candidates.append(
                _ImageCandidate(
                    page=int(columns[0]),
                    number=int(columns[1]),
                    image_type=columns[2].casefold(),
                    width=int(columns[3]),
                    height=int(columns[4]),
                )
            )
        except ValueError:
            continue
    return tuple(candidates)


def _has_safe_photo_dimensions(width: int, height: int) -> bool:
    """Return whether dimensions fit the conservative profile-photo bounds."""
    return (
        PHOTO_MIN_SOURCE_DIMENSION <= width <= PHOTO_MAX_SOURCE_DIMENSION
        and PHOTO_MIN_SOURCE_DIMENSION <= height <= PHOTO_MAX_SOURCE_DIMENSION
        and width * height <= PHOTO_MAX_SOURCE_PIXELS
        and width * 100 >= height * 95
        and width * 100 <= height * 105
    )


def _is_safe_photo_candidate(candidate: _ImageCandidate) -> bool:
    """Return whether a listed non-mask image is safe and profile-shaped."""
    return candidate.image_type not in {"mask", "smask"} and (
        _has_safe_photo_dimensions(candidate.width, candidate.height)
    )


def _parse_layout_images(output: str) -> tuple[_LayoutImage, ...]:
    """Parse displayed image geometry from ``pdftohtml -xml`` output."""
    try:
        root = ElementTree.fromstring(output)
    except ElementTree.ParseError as exc:
        raise ValueError("pdftohtml returned malformed image layout XML.") from exc

    images: list[_LayoutImage] = []
    for element in root.iter():
        if _local_name(element) != "image":
            continue
        try:
            image = _LayoutImage(
                left=float(element.attrib["left"]),
                top=float(element.attrib["top"]),
                width=float(element.attrib["width"]),
                height=float(element.attrib["height"]),
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(
                "pdftohtml returned an image with invalid layout geometry."
            ) from exc
        if image.width <= 0 or image.height <= 0:
            raise ValueError(
                "pdftohtml returned an image with invalid layout geometry."
            )
        images.append(image)
    return tuple(images)


def _is_profile_layout_image(image: _LayoutImage) -> bool:
    """Return whether displayed geometry matches the observed profile region."""
    return (
        PROFILE_LAYOUT_LEFT_RANGE[0] <= image.left <= PROFILE_LAYOUT_LEFT_RANGE[1]
        and PROFILE_LAYOUT_TOP_RANGE[0] <= image.top <= PROFILE_LAYOUT_TOP_RANGE[1]
        and PROFILE_LAYOUT_SIZE_RANGE[0] <= image.width <= PROFILE_LAYOUT_SIZE_RANGE[1]
        and PROFILE_LAYOUT_SIZE_RANGE[0] <= image.height <= PROFILE_LAYOUT_SIZE_RANGE[1]
        and image.width * 100 >= image.height * 90
        and image.width * 100 <= image.height * 110
    )


def _jpeg_bytes(image_path: Path) -> tuple[bytes, int, int]:
    """Convert an extracted image to the deterministic member JPEG format."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(image_path) as source_image:
            if not _has_safe_photo_dimensions(*source_image.size):
                raise _UnsafePhotoError(
                    "Extracted image dimensions are outside safe profile-photo bounds."
                )

            source_image.load()
            image = ImageOps.exif_transpose(source_image)
            image.thumbnail(
                (STAGED_PHOTO_MAX_DIMENSION, STAGED_PHOTO_MAX_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            output = io.BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=STAGED_PHOTO_JPEG_QUALITY,
                optimize=True,
            )
            return output.getvalue(), image.width, image.height


def _photo_error(path: Path, code: str, message: str) -> PhotoStageResult:
    """Return a consistent failed photo staging result."""
    return PhotoStageResult(
        source_path=path,
        status=PhotoStageStatus.ERROR,
        manifest=None,
        issues=(SourceIssue(source_path=path, code=code, message=message),),
    )


def stage_pdf_photo(
    path: str | Path,
    staging_directory: str | Path,
    *,
    output_name: str | None = None,
) -> PhotoStageResult:
    """Stage one unambiguous embedded photo inside an explicit directory.

    When ``output_name`` is omitted, the JPEG filename is its SHA256 digest.
    An explicit name must be a plain ``.jpg`` filename and cannot escape the
    supplied existing staging directory.
    """
    source_path = Path(path)
    staging_path = Path(staging_directory)
    if not source_path.is_file():
        return _photo_error(source_path, "missing_pdf", "Source PDF does not exist.")
    if not staging_path.is_dir() or staging_path.is_symlink():
        return _photo_error(
            source_path,
            "invalid_staging_directory",
            "Photo staging directory must be an existing non-symlink directory.",
        )
    if output_name is not None:
        requested_name = Path(output_name)
        if (
            requested_name.name != output_name
            or requested_name.suffix.casefold() not in {".jpg", ".jpeg"}
        ):
            return _photo_error(
                source_path,
                "invalid_output_name",
                "Photo output name must be a plain .jpg or .jpeg filename.",
            )

    try:
        listed = subprocess.run(
            ["pdfimages", "-list", str(source_path)],
            capture_output=True,
            check=False,
            text=True,
            timeout=PDFIMAGES_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return _photo_error(
            source_path,
            "pdfimages_list_timeout",
            f"pdfimages -list exceeded the {PDFIMAGES_TIMEOUT_SECONDS}-second timeout.",
        )
    except OSError as exc:
        return _photo_error(
            source_path,
            "pdfimages_unavailable",
            f"Poppler pdfimages could not be executed: {exc}",
        )
    if listed.returncode:
        return _photo_error(
            source_path,
            "pdfimages_list_failed",
            f"pdfimages -list failed: {listed.stderr.strip() or 'unknown error'}",
        )

    candidates = _parse_image_candidates(listed.stdout)
    non_mask_candidates = [
        candidate
        for candidate in candidates
        if candidate.image_type not in {"mask", "smask"}
    ]
    if not non_mask_candidates:
        return PhotoStageResult(
            source_path=source_path,
            status=PhotoStageStatus.MISSING,
            manifest=None,
            issues=(
                SourceIssue(
                    source_path=source_path,
                    code="photo_missing",
                    message="PDF has no non-mask image.",
                    severity="warning",
                ),
            ),
        )
    if len(non_mask_candidates) > 1:
        return PhotoStageResult(
            source_path=source_path,
            status=PhotoStageStatus.AMBIGUOUS,
            manifest=None,
            issues=(
                SourceIssue(
                    source_path=source_path,
                    code="photo_ambiguous",
                    message="PDF has more than one non-mask image.",
                    severity="warning",
                ),
            ),
        )

    candidate = non_mask_candidates[0]
    if not _is_safe_photo_candidate(candidate):
        return PhotoStageResult(
            source_path=source_path,
            status=PhotoStageStatus.MISSING,
            manifest=None,
            issues=(
                SourceIssue(
                    source_path=source_path,
                    code="photo_unsafe",
                    message=(
                        "PDF non-mask image does not meet safe profile-photo bounds."
                    ),
                    severity="warning",
                ),
            ),
        )

    try:
        with tempfile.TemporaryDirectory(
            dir=staging_path, prefix=".pdf-layout-"
        ) as layout_directory:
            layout = subprocess.run(
                [
                    "pdftohtml",
                    "-xml",
                    "-stdout",
                    "-hidden",
                    str(source_path.resolve()),
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=PDFTOHTML_TIMEOUT_SECONDS,
                cwd=layout_directory,
            )
    except subprocess.TimeoutExpired:
        return _photo_error(
            source_path,
            "pdftohtml_timeout",
            f"pdftohtml exceeded the {PDFTOHTML_TIMEOUT_SECONDS}-second timeout.",
        )
    except OSError as exc:
        return _photo_error(
            source_path,
            "pdftohtml_unavailable",
            f"Poppler pdftohtml could not be executed: {exc}",
        )
    if layout.returncode:
        return _photo_error(
            source_path,
            "pdftohtml_failed",
            f"pdftohtml failed: {layout.stderr.strip() or 'unknown error'}",
        )
    try:
        layout_images = _parse_layout_images(layout.stdout)
    except ValueError as exc:
        return _photo_error(source_path, "invalid_pdf_image_layout", str(exc))

    if not layout_images:
        return PhotoStageResult(
            source_path=source_path,
            status=PhotoStageStatus.MISSING,
            manifest=None,
            issues=(
                SourceIssue(
                    source_path=source_path,
                    code="photo_layout_missing",
                    message="PDF has no displayed image in its layout XML.",
                    severity="warning",
                ),
            ),
        )
    if len(layout_images) != 1 or not _is_profile_layout_image(layout_images[0]):
        return PhotoStageResult(
            source_path=source_path,
            status=PhotoStageStatus.AMBIGUOUS,
            manifest=None,
            issues=(
                SourceIssue(
                    source_path=source_path,
                    code="photo_layout_ambiguous",
                    message=(
                        "PDF displayed images do not uniquely match the profile region."
                    ),
                    severity="warning",
                ),
            ),
        )

    try:
        with tempfile.TemporaryDirectory(
            dir=staging_path, prefix=".pdf-photo-"
        ) as temporary_directory:
            extraction_prefix = Path(temporary_directory) / "image"
            extracted = subprocess.run(
                ["pdfimages", "-all", str(source_path), str(extraction_prefix)],
                capture_output=True,
                check=False,
                text=True,
                timeout=PDFIMAGES_TIMEOUT_SECONDS,
            )
            if extracted.returncode:
                return _photo_error(
                    source_path,
                    "pdfimages_extract_failed",
                    (
                        "pdfimages -all failed: "
                        f"{extracted.stderr.strip() or 'unknown error'}"
                    ),
                )

            candidate_prefix = f"image-{candidate.number:03d}."
            image_paths = [
                image_path
                for image_path in Path(temporary_directory).iterdir()
                if image_path.is_file() and image_path.name.startswith(candidate_prefix)
            ]
            if len(image_paths) != 1:
                return _photo_error(
                    source_path,
                    "photo_extraction_mismatch",
                    (
                        "Extracted image could not be matched unambiguously to "
                        "pdfimages -list."
                    ),
                )
            jpeg, width, height = _jpeg_bytes(image_paths[0])
    except subprocess.TimeoutExpired:
        return _photo_error(
            source_path,
            "pdfimages_extract_timeout",
            f"pdfimages -all exceeded the {PDFIMAGES_TIMEOUT_SECONDS}-second timeout.",
        )
    except FileNotFoundError:
        return _photo_error(
            source_path,
            "pdfimages_unavailable",
            "Poppler pdfimages is not installed or not executable.",
        )
    except (
        _UnsafePhotoError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        return _photo_error(
            source_path,
            "photo_unsafe",
            f"Embedded photo is unsafe to decode: {exc}",
        )
    except (OSError, UnidentifiedImageError) as exc:
        return _photo_error(
            source_path,
            "photo_conversion_failed",
            f"Embedded photo could not be converted: {exc}",
        )

    digest = hashlib.sha256(jpeg).hexdigest()
    staged_path = staging_path / (output_name or f"{digest}.jpg")
    if staged_path.is_symlink():
        return _photo_error(
            source_path,
            "photo_output_conflict",
            "Staged photo path cannot be a symbolic link.",
        )
    if staged_path.exists():
        try:
            existing_digest = hashlib.sha256(staged_path.read_bytes()).hexdigest()
        except OSError as exc:
            return _photo_error(
                source_path,
                "photo_write_failed",
                f"Existing staged photo could not be read: {exc}",
            )
        if existing_digest != digest:
            return _photo_error(
                source_path,
                "photo_output_conflict",
                "Staged photo path already contains different content.",
            )
    else:
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(staged_path, flags, 0o600)
            with os.fdopen(descriptor, "wb") as staged_file:
                staged_file.write(jpeg)
        except FileExistsError:
            return _photo_error(
                source_path,
                "photo_output_conflict",
                "Staged photo path was created concurrently.",
            )
        except OSError as exc:
            return _photo_error(
                source_path,
                "photo_write_failed",
                f"Staged photo could not be written: {exc}",
            )

    return PhotoStageResult(
        source_path=source_path,
        status=PhotoStageStatus.STAGED,
        manifest=PhotoManifestEntry(
            source_path=source_path,
            staged_path=staged_path,
            sha256=digest,
            byte_size=len(jpeg),
            width=width,
            height=height,
            source_page=candidate.page,
            source_image_number=candidate.number,
            source_width=candidate.width,
            source_height=candidate.height,
        ),
        issues=(),
    )
