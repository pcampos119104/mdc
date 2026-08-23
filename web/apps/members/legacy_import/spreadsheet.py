"""Read the approved legacy XLSX source without coercing cell values."""

import posixpath
import re
from datetime import date
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from .normalization import excel_serial_to_date, parse_brazilian_date
from .records import SourceIssue, SpreadsheetReadResult, SpreadsheetRecord


SHEET_NAME = "Listagem de Pessoas"
EXPECTED_HEADERS = (
    "Nome",
    "Identificação",
    "Tipo de Pessoa",
    "Tipo de Membro",
    "Nascimento",
    "Logradouro",
    "Número",
    "Complemento",
    "Bairro",
    "Cidade",
    "Estado",
    "Telefone Celular",
    "Telefone Residencial",
    "Telefone Comercial",
    "Telefone Contato",
    "E-mail",
    "Participa Grupo",
)

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOCUMENT_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REFERENCE = re.compile(r"^(?P<column>[A-Z]+)(?P<row>\d+)$")


class SpreadsheetReadError(ValueError):
    """Report a structural or unsupported workbook error."""


def _qualified(name: str) -> str:
    """Return an OOXML main-namespace tag name."""
    return f"{{{_MAIN_NS}}}{name}"


def _parse_xml(archive: ZipFile, member: str) -> ElementTree.Element:
    """Read and parse one required XML member from an OOXML archive."""
    try:
        return ElementTree.fromstring(archive.read(member))
    except KeyError as exc:
        raise SpreadsheetReadError(
            f"Malformed XLSX workbook: missing {member}."
        ) from exc
    except ElementTree.ParseError as exc:
        raise SpreadsheetReadError(
            f"Malformed XLSX workbook: invalid XML in {member}."
        ) from exc


def _column_index(reference: str) -> int:
    """Convert an Excel cell reference to a zero-based column index."""
    match = _CELL_REFERENCE.fullmatch(reference.upper())
    if not match:
        raise SpreadsheetReadError(
            f"Malformed XLSX workbook: invalid cell reference {reference!r}."
        )

    index = 0
    for character in match.group("column"):
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def _rich_text(element: ElementTree.Element) -> str:
    """Join plain or rich OOXML string text without normalizing it."""
    return "".join(node.text or "" for node in element.iter(_qualified("t")))


def _shared_strings(archive: ZipFile) -> tuple[str, ...]:
    """Return shared strings when the optional OOXML table exists."""
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return ()
    except ElementTree.ParseError as exc:
        raise SpreadsheetReadError(
            "Malformed XLSX workbook: invalid XML in xl/sharedStrings.xml."
        ) from exc
    return tuple(_rich_text(item) for item in root.findall(_qualified("si")))


def _cell_value(
    cell: ElementTree.Element, shared_strings: tuple[str, ...]
) -> tuple[str, str | None]:
    """Return a cell's raw string and declared OOXML type."""
    if cell.find(_qualified("f")) is not None:
        reference = cell.get("r", "unknown")
        raise SpreadsheetReadError(
            f"Formula cells are not supported in legacy XLSX sources: {reference}."
        )

    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(_qualified("is"))
        return (_rich_text(inline) if inline is not None else "", cell_type)

    value_element = cell.find(_qualified("v"))
    raw_value = value_element.text or "" if value_element is not None else ""
    if cell_type != "s" or not raw_value:
        return raw_value, cell_type

    try:
        shared_string_index = int(raw_value)
    except ValueError as exc:
        raise SpreadsheetReadError(
            f"Malformed XLSX workbook: invalid shared string index {raw_value!r}."
        ) from exc
    if shared_string_index < 0 or shared_string_index >= len(shared_strings):
        raise SpreadsheetReadError(
            f"Malformed XLSX workbook: invalid shared string index {raw_value!r}."
        )
    return shared_strings[shared_string_index], cell_type


def _row_values(
    row: ElementTree.Element, shared_strings: tuple[str, ...]
) -> dict[int, tuple[str, str | None]]:
    """Return sparse raw values keyed by zero-based spreadsheet column."""
    values: dict[int, tuple[str, str | None]] = {}
    next_column = 0
    for cell in row.findall(_qualified("c")):
        reference = cell.get("r")
        column = _column_index(reference) if reference else next_column
        if column in values:
            raise SpreadsheetReadError(
                f"Malformed XLSX workbook: duplicate cell in column {column + 1}."
            )
        values[column] = _cell_value(cell, shared_strings)
        next_column = column + 1
    return values


def _worksheet_path(archive: ZipFile, workbook: ElementTree.Element) -> str:
    """Validate the sole worksheet and resolve its OOXML relationship."""
    sheets = workbook.findall(f"{_qualified('sheets')}/{_qualified('sheet')}")
    if len(sheets) != 1 or sheets[0].get("name") != SHEET_NAME:
        names = [sheet.get("name", "") for sheet in sheets]
        raise SpreadsheetReadError(
            f"Expected one worksheet named {SHEET_NAME!r}; found {names!r}."
        )

    relationship_id = sheets[0].get(f"{{{_DOCUMENT_REL_NS}}}id")
    if not relationship_id:
        raise SpreadsheetReadError(
            "Malformed XLSX workbook: worksheet relationship is missing."
        )

    relationships = _parse_xml(archive, "xl/_rels/workbook.xml.rels")
    relationship = next(
        (
            item
            for item in relationships.findall(f"{{{_PACKAGE_REL_NS}}}Relationship")
            if item.get("Id") == relationship_id
        ),
        None,
    )
    if relationship is None or relationship.get("TargetMode") == "External":
        raise SpreadsheetReadError(
            "Malformed XLSX workbook: worksheet relationship is invalid."
        )

    target = relationship.get("Target", "")
    if target.startswith("/"):
        worksheet_path = posixpath.normpath(target.lstrip("/"))
    else:
        worksheet_path = posixpath.normpath(posixpath.join("xl", target))
    if worksheet_path.startswith("../") or worksheet_path == "..":
        raise SpreadsheetReadError(
            "Malformed XLSX workbook: worksheet path escapes the archive root."
        )
    return worksheet_path


def _source_row(row: ElementTree.Element, fallback: int) -> int:
    """Return the declared source row number or a safe positional fallback."""
    raw_row = row.get("r")
    if raw_row is None:
        return fallback
    try:
        source_row = int(raw_row)
    except ValueError as exc:
        raise SpreadsheetReadError(
            f"Malformed XLSX workbook: invalid row number {raw_row!r}."
        ) from exc
    if source_row < 1:
        raise SpreadsheetReadError(
            f"Malformed XLSX workbook: invalid row number {raw_row!r}."
        )
    return source_row


def _read_birth_date(
    raw_value: str, cell_type: str | None, *, date_1904: bool
) -> date | None:
    """Read a birth date from either an Excel serial or source text."""
    if not raw_value:
        return None
    if cell_type in {None, "n"}:
        return excel_serial_to_date(raw_value, date_1904=date_1904)
    parsed = parse_brazilian_date(raw_value)
    if parsed is None:
        raise ValueError(f"Invalid Brazilian date: {raw_value!r}")
    return parsed


def _record_from_row(
    path: Path,
    source_row: int,
    ordinal: int,
    values: dict[int, tuple[str, str | None]],
    *,
    date_1904: bool,
) -> tuple[SpreadsheetRecord, tuple[SourceIssue, ...]]:
    """Build one spreadsheet record while retaining all raw source fields."""
    raw_fields = {
        header: values.get(index, ("", None))[0]
        for index, header in enumerate(EXPECTED_HEADERS)
    }
    issues: list[SourceIssue] = []
    birth_date_raw, birth_cell_type = values.get(4, ("", None))
    try:
        birth_date = _read_birth_date(
            birth_date_raw, birth_cell_type, date_1904=date_1904
        )
    except ValueError:
        birth_date = None
        issues.append(
            SourceIssue(
                source_path=path,
                source_row=source_row,
                field="Nascimento",
                raw_value=birth_date_raw,
                code="invalid_birth_date",
                message="Nascimento is not a valid Excel serial or Brazilian date.",
            )
        )

    if not raw_fields["Nome"]:
        issues.append(
            SourceIssue(
                source_path=path,
                source_row=source_row,
                field="Nome",
                raw_value="",
                code="missing_name",
                message="Spreadsheet row has no member name.",
            )
        )

    for column, (raw_value, _cell_type) in values.items():
        if column >= len(EXPECTED_HEADERS) and raw_value:
            issues.append(
                SourceIssue(
                    source_path=path,
                    source_row=source_row,
                    raw_value=raw_value,
                    code="unexpected_cell",
                    message=(
                        f"Source row contains data in unexpected column {column + 1}."
                    ),
                    severity="warning",
                )
            )

    record = SpreadsheetRecord(
        source_path=path,
        source_row=source_row,
        ordinal=ordinal,
        name_raw=raw_fields["Nome"],
        identification_raw=raw_fields["Identificação"],
        person_type_raw=raw_fields["Tipo de Pessoa"],
        member_type_raw=raw_fields["Tipo de Membro"],
        birth_date_raw=birth_date_raw,
        birth_date=birth_date,
        street_raw=raw_fields["Logradouro"],
        street_number_raw=raw_fields["Número"],
        complement_raw=raw_fields["Complemento"],
        district_raw=raw_fields["Bairro"],
        city_raw=raw_fields["Cidade"],
        state_raw=raw_fields["Estado"],
        mobile_phone_raw=raw_fields["Telefone Celular"],
        home_phone_raw=raw_fields["Telefone Residencial"],
        work_phone_raw=raw_fields["Telefone Comercial"],
        contact_phone_raw=raw_fields["Telefone Contato"],
        email_raw=raw_fields["E-mail"],
        group_participation_raw=raw_fields["Participa Grupo"],
        raw_fields=raw_fields,
    )
    return record, tuple(issues)


def read_spreadsheet(path: str | Path) -> SpreadsheetReadResult:
    """Read the approved XLSX worksheet and preserve every source cell string."""
    source_path = Path(path)
    suffix = source_path.suffix.casefold()
    if suffix == ".xls":
        raise SpreadsheetReadError(
            "Legacy .xls workbooks are not supported; provide an .xlsx workbook."
        )
    if suffix != ".xlsx":
        raise SpreadsheetReadError("Expected a workbook with the .xlsx extension.")

    try:
        with ZipFile(source_path) as archive:
            workbook = _parse_xml(archive, "xl/workbook.xml")
            worksheet_path = _worksheet_path(archive, workbook)
            worksheet = _parse_xml(archive, worksheet_path)
            shared_strings = _shared_strings(archive)

            workbook_properties = workbook.find(_qualified("workbookPr"))
            date_1904 = (
                workbook_properties is not None
                and workbook_properties.get("date1904", "").casefold()
                in {"1", "true"}
            )

            sheet_data = worksheet.find(_qualified("sheetData"))
            rows = (
                [] if sheet_data is None else sheet_data.findall(_qualified("row"))
            )
            if not rows:
                raise SpreadsheetReadError(
                    "Malformed XLSX workbook: worksheet contains no header row."
                )

            header_values = _row_values(rows[0], shared_strings)
            headers = tuple(
                header_values.get(index, ("", None))[0]
                for index in range(len(EXPECTED_HEADERS))
            )
            extra_headers = [
                raw_value
                for index, (raw_value, _cell_type) in header_values.items()
                if index >= len(EXPECTED_HEADERS) and raw_value
            ]
            if headers != EXPECTED_HEADERS or extra_headers:
                raise SpreadsheetReadError(
                    "Unexpected XLSX headers. Expected exactly: "
                    + ", ".join(EXPECTED_HEADERS)
                )

            records: list[SpreadsheetRecord] = []
            issues: list[SourceIssue] = []
            for fallback_row, row in enumerate(rows[1:], start=2):
                values = _row_values(row, shared_strings)
                if not any(raw_value for raw_value, _cell_type in values.values()):
                    continue
                source_row = _source_row(row, fallback_row)
                record, row_issues = _record_from_row(
                    source_path,
                    source_row,
                    len(records) + 1,
                    values,
                    date_1904=date_1904,
                )
                records.append(record)
                issues.extend(row_issues)
    except SpreadsheetReadError:
        raise
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise SpreadsheetReadError(
            f"Cannot read XLSX workbook {source_path}: {exc}"
        ) from exc

    return SpreadsheetReadResult(
        source_path=source_path,
        headers=EXPECTED_HEADERS,
        records=tuple(records),
        issues=tuple(issues),
    )
