"""Data contracts shared by the read-only legacy import readers."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Literal, Mapping


IssueSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class SourceIssue:
    """Describe a source problem without changing or guessing its value."""

    source_path: Path
    code: str
    message: str
    severity: IssueSeverity = "error"
    source_row: int | None = None
    field: str | None = None
    raw_value: str | None = None


@dataclass(frozen=True, slots=True)
class SpreadsheetRecord:
    """Represent one source row from the legacy member spreadsheet."""

    source_path: Path
    source_row: int
    ordinal: int
    name_raw: str
    identification_raw: str
    person_type_raw: str
    member_type_raw: str
    birth_date_raw: str
    birth_date: date | None
    street_raw: str
    street_number_raw: str
    complement_raw: str
    district_raw: str
    city_raw: str
    state_raw: str
    mobile_phone_raw: str
    home_phone_raw: str
    work_phone_raw: str
    contact_phone_raw: str
    email_raw: str
    group_participation_raw: str
    raw_fields: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class SpreadsheetReadResult:
    """Contain spreadsheet records and non-structural source issues."""

    source_path: Path
    headers: tuple[str, ...]
    records: tuple[SpreadsheetRecord, ...]
    issues: tuple[SourceIssue, ...]


class PDFSourceKind(StrEnum):
    """Classify the supported PDF filename families."""

    MEMBER = "member"
    AGGREGATE = "aggregate"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PDFSource:
    """Describe information carried by a legacy PDF filename."""

    source_path: Path
    kind: PDFSourceKind
    ordinal: int | None
    name_raw: str


@dataclass(frozen=True, slots=True)
class PDFOccurrence:
    """Represent one repeatable occurrence type and date from a PDF."""

    ordinal: int
    occurrence_type_raw: str
    occurrence_date_raw: str
    occurrence_date: date


@dataclass(frozen=True, slots=True)
class PDFRecord:
    """Represent destination-relevant fields read from one member PDF."""

    source_path: Path
    source: PDFSource
    registration_type_raw: str
    person_type_raw: str
    name_raw: str
    cpf_raw: str
    birth_date_raw: str
    sex_raw: str
    identification_raw: str
    nationality_raw: str
    birthplace_raw: str
    email_raw: str
    contact_name_raw: str
    mobile_phone_raw: str
    home_phone_raw: str
    father_name_raw: str
    mother_name_raw: str
    spouse_name_raw: str
    marital_status_raw: str
    postal_code_raw: str
    country_raw: str
    state_raw: str
    city_raw: str
    street_raw: str
    street_number_raw: str
    complement_raw: str
    district_raw: str
    occurrences: tuple[PDFOccurrence, ...]
    raw_fields: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class PDFReadResult:
    """Contain a parsed member PDF, its classification, and parse issues."""

    source_path: Path
    source: PDFSource
    record: PDFRecord | None
    issues: tuple[SourceIssue, ...]


class PhotoStageStatus(StrEnum):
    """Describe the result of conservative PDF photo staging."""

    STAGED = "staged"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PhotoManifestEntry:
    """Describe a staged JPEG for a later import manifest."""

    source_path: Path
    staged_path: Path
    sha256: str
    byte_size: int
    width: int
    height: int
    source_page: int
    source_image_number: int
    source_width: int
    source_height: int


@dataclass(frozen=True, slots=True)
class PhotoStageResult:
    """Contain the conservative photo decision and optional staged artifact."""

    source_path: Path
    status: PhotoStageStatus
    manifest: PhotoManifestEntry | None
    issues: tuple[SourceIssue, ...]
