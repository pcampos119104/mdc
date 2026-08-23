"""Focused tests for read-only legacy import source readers."""

import hashlib
import subprocess
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from PIL import Image

from apps.members.legacy_import import (
    EXPECTED_HEADERS,
    PDFSourceKind,
    PhotoStageStatus,
    SpreadsheetReadError,
    brazilian_state_to_uf,
    classify_pdf_source,
    clean_preserved_text,
    comparison_key,
    digits_only,
    excel_serial_to_date,
    normalize_cep,
    normalize_cpf,
    normalize_email,
    normalize_phone,
    parse_brazilian_date,
    parse_pdf_filename,
    read_pdf,
    read_spreadsheet,
    stage_pdf_photo,
)
from apps.members.legacy_import.pdf import (
    PDFIMAGES_TIMEOUT_SECONDS,
    PDFTOHTML_TIMEOUT_SECONDS,
    PDFTOTEXT_TIMEOUT_SECONDS,
)


def _inline_cell(reference: str, value: str) -> str:
    """Return one inline-string worksheet cell."""
    return (
        f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">'
        f"{escape(value)}</t></is></c>"
    )


def _write_test_xlsx(
    path: Path,
    *,
    formula_cell: bool = False,
    negative_shared_string: bool = False,
) -> None:
    """Write a tiny anonymized OOXML workbook without spreadsheet libraries."""
    header_cells = "".join(
        _inline_cell(f"{chr(ord('A') + index)}1", header)
        for index, header in enumerate(EXPECTED_HEADERS)
    )
    if formula_cell:
        identification_cell = '<c r="B7" t="n"><f>100 + 23</f><v>123</v></c>'
    elif negative_shared_string:
        identification_cell = '<c r="B7" t="s"><v>-1</v></c>'
    else:
        identification_cell = '<c r="B7" t="n"><v>000123</v></c>'
    data_cells = "".join(
        (
            _inline_cell("A7", "  Pessôa   Teste  "),
            identification_cell,
            _inline_cell("C7", "Pessoa"),
            _inline_cell("D7", "Membro"),
            '<c r="E7" t="n"><v>45292</v></c>',
            _inline_cell("F7", "Rua Exemplo"),
            '<c r="G7" t="n"><v>0012</v></c>',
            _inline_cell("J7", "Cidade Teste"),
            _inline_cell("K7", "São Paulo"),
            '<c r="L7" t="n"><v>01199887766</v></c>',
            _inline_cell("P7", "Pessoa.Teste@Example.org"),
        )
    )
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Listagem de Pessoas" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    relationships = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
   Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
   Target="worksheets/sheet1.xml"/>
</Relationships>"""
    worksheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">{header_cells}</row>
    <row r="7">{data_cells}</row>
  </sheetData>
</worksheet>"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
</Types>"""

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
        if negative_shared_string:
            archive.writestr(
                "xl/sharedStrings.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <si><t>not the requested string</t></si>
</sst>""",
            )


def _bbox_xhtml(*, ambiguous_cpf: bool = False) -> str:
    """Return minimal anonymized Poppler-like bbox XHTML."""
    lines = [
        (300, 100, "Nome"),
        (300, 120, "PESSOA TESTE"),
        (10, 160, "CPF"),
        (200, 160, "Nascimento"),
        (10, 180, "529.982.247-25"),
        (200, 180, "2/1/2000"),
        (300, 300, "Principais Ocorrências"),
        (10, 340, "BATISMO"),
        (200, 340, "ACLAMAÇÃO"),
        (10, 355, "3/2/2020"),
        (200, 355, "4/3/2021"),
        (10, 380, "Local da Ocorrência"),
    ]
    if ambiguous_cpf:
        lines.append((10, 195, "111.111.111-11"))
    xml_lines = "".join(
        (
            f'<line xMin="{x}" yMin="{y}" xMax="{x + 100}" '
            f'yMax="{y + 10}"><word>{escape(text)}</word></line>'
        )
        for x, y, text in lines
    )
    return (
        '<html xmlns="http://www.w3.org/1999/xhtml"><body><doc>'
        f'<page width="800" height="1000"><flow><block>{xml_lines}</block></flow></page>'
        "</doc></body></html>"
    )


def _image_layout_xml(
    images: tuple[tuple[int, int, int, int], ...] = ((59, 503, 111, 111),),
) -> str:
    """Return minimal anonymized pdftohtml image layout XML."""
    image_elements = "".join(
        f'<image left="{left}" top="{top}" width="{width}" height="{height}"/>'
        for left, top, width, height in images
    )
    return f"<pdf2xml><page>{image_elements}</page></pdf2xml>"


def test_normalization_keeps_output_cleaning_separate_from_comparison() -> None:
    """Display cleaning should preserve text that comparison keys discard."""
    assert clean_preserved_text("  D'Ávila\n  Júnior ") == "D'Ávila Júnior"
    assert comparison_key(" D'ÁVILA -- Júnior ") == "d avila junior"
    assert digits_only("CPF １２3.٤") == "1234"


def test_structured_brazilian_normalizers_validate_values() -> None:
    """Structured helpers should clean valid values and reject malformed ones."""
    assert normalize_cpf("529.982.247-25") == "52998224725"
    assert normalize_cpf("111.111.111-11") is None
    assert normalize_phone("+55 (11) 99887-7665") == "5511998877665"
    assert normalize_phone("123") is None
    assert normalize_cep("01001-000") == "01001000"
    assert normalize_cep("100") is None
    assert normalize_email(" Pessoa.Teste@Example.ORG ") == "pessoa.teste@example.org"
    assert normalize_email("sem-arroba.example.org") is None
    assert normalize_email("pessoa..teste@example.org") is None
    assert normalize_email("pessoa@-example.org") is None


def test_date_and_state_normalization_support_legacy_forms() -> None:
    """Date and state helpers should accept sampled Brazilian source forms."""
    assert parse_brazilian_date("4/8/1997") == date(1997, 8, 4)
    assert parse_brazilian_date("04.08.1997") == date(1997, 8, 4)
    assert parse_brazilian_date("1997-08-04") == date(1997, 8, 4)
    assert parse_brazilian_date("31/2/2000") is None
    assert excel_serial_to_date("45292") == date(2024, 1, 1)
    assert brazilian_state_to_uf("São Paulo") == "SP"
    assert brazilian_state_to_uf("sp") == "SP"
    assert brazilian_state_to_uf("estado desconhecido") is None


def test_read_spreadsheet_preserves_raw_numeric_cells_and_source_position(
    tmp_path: Path,
) -> None:
    """The XLSX reader should avoid coercion while converting date serials."""
    workbook_path = tmp_path / "legacy.xlsx"
    _write_test_xlsx(workbook_path)

    result = read_spreadsheet(workbook_path)

    assert result.headers == EXPECTED_HEADERS
    assert result.issues == ()
    assert len(result.records) == 1
    record = result.records[0]
    assert record.source_row == 7
    assert record.ordinal == 1
    assert record.name_raw == "  Pessôa   Teste  "
    assert record.identification_raw == "000123"
    assert record.street_number_raw == "0012"
    assert record.mobile_phone_raw == "01199887766"
    assert record.birth_date_raw == "45292"
    assert record.birth_date == date(2024, 1, 1)


def test_read_spreadsheet_rejects_xls_and_malformed_xlsx(tmp_path: Path) -> None:
    """Unsupported or malformed workbooks should fail with clear source errors."""
    with pytest.raises(SpreadsheetReadError, match=r"\.xls workbooks"):
        read_spreadsheet(tmp_path / "legacy.xls")

    malformed = tmp_path / "malformed.xlsx"
    malformed.write_bytes(b"not a ZIP archive")
    with pytest.raises(SpreadsheetReadError, match="Cannot read XLSX workbook"):
        read_spreadsheet(malformed)


def test_read_spreadsheet_rejects_formula_cells(tmp_path: Path) -> None:
    """Formula cells should never expose absent or stale cached values."""
    workbook_path = tmp_path / "formula.xlsx"
    _write_test_xlsx(workbook_path, formula_cell=True)

    with pytest.raises(SpreadsheetReadError, match=r"Formula cells.*B7"):
        read_spreadsheet(workbook_path)


def test_read_spreadsheet_rejects_negative_shared_string_indexes(
    tmp_path: Path,
) -> None:
    """Negative shared-string indexes should not use Python reverse indexing."""
    workbook_path = tmp_path / "negative-shared-string.xlsx"
    _write_test_xlsx(workbook_path, negative_shared_string=True)

    with pytest.raises(SpreadsheetReadError, match=r"shared string index '-1'"):
        read_spreadsheet(workbook_path)


def test_pdf_filename_parsing_classifies_member_and_aggregate_sources() -> None:
    """Numbered member PDFs and the aggregate listing should remain distinct."""
    member = parse_pdf_filename("007 Pessoa Teste.pdf")
    assert member.kind == PDFSourceKind.MEMBER
    assert member.ordinal == 7
    assert member.name_raw == "Pessoa Teste"
    assert classify_pdf_source("Listagem de Pessoas.pdf") == PDFSourceKind.AGGREGATE
    assert classify_pdf_source("sem-prefixo.pdf") == PDFSourceKind.UNKNOWN


def test_read_pdf_uses_bbox_geometry_and_extracts_repeatable_occurrences(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The PDF reader should map nearby raw values and occurrence pairs."""
    pdf_path = tmp_path / "001 PESSOA TESTE.pdf"
    pdf_path.write_bytes(b"mock PDF")
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return mocked Poppler geometry and retain its exact invocation."""
        assert kwargs["timeout"] == PDFTOTEXT_TIMEOUT_SECONDS
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, _bbox_xhtml(), "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = read_pdf(pdf_path)

    assert calls == [["pdftotext", "-bbox-layout", str(pdf_path), "-"]]
    assert result.record is not None
    assert result.record.name_raw == "PESSOA TESTE"
    assert result.record.cpf_raw == "529.982.247-25"
    assert result.record.birth_date_raw == "2/1/2000"
    assert result.record.raw_fields["Nome"] == "PESSOA TESTE"
    assert len(result.record.occurrences) == 2
    assert result.record.occurrences[0].occurrence_type_raw == "BATISMO"
    assert result.record.occurrences[0].occurrence_date == date(2020, 2, 3)
    assert result.record.occurrences[1].occurrence_type_raw == "ACLAMAÇÃO"
    assert result.record.occurrences[1].occurrence_date == date(2021, 3, 4)


def test_read_pdf_returns_stable_issue_when_pdftotext_times_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A stalled pdftotext process should become a stable source issue."""
    pdf_path = tmp_path / "002 OUTRA PESSOA.pdf"
    pdf_path.write_bytes(b"mock PDF")

    def fake_run(command: list[str], **kwargs: object) -> None:
        """Simulate Poppler exceeding its configured deadline."""
        timeout = kwargs["timeout"]
        assert isinstance(timeout, (int, float))
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = read_pdf(pdf_path)

    assert result.record is None
    assert [issue.code for issue in result.issues] == ["pdftotext_timeout"]


def test_read_pdf_rejects_field_values_on_independent_baselines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Multiple vertical field candidates should block extraction as ambiguous."""
    pdf_path = tmp_path / "002 OUTRA PESSOA.pdf"
    pdf_path.write_bytes(b"mock PDF")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, _bbox_xhtml(ambiguous_cpf=True), ""
        ),
    )

    result = read_pdf(pdf_path)

    assert result.record is not None
    assert result.record.cpf_raw == ""
    assert result.record.raw_fields["CPF"] == ""
    ambiguity = [
        issue for issue in result.issues if issue.code == "ambiguous_field_value"
    ]
    assert len(ambiguity) == 1
    assert ambiguity[0].field == "CPF"
    assert ambiguity[0].severity == "error"
    assert ambiguity[0].raw_value == "529.982.247-25\n111.111.111-11"


def test_read_pdf_returns_an_issue_for_invalid_geometry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Malformed Poppler geometry should become a parse issue, not guessed data."""
    pdf_path = tmp_path / "002 OUTRA PESSOA.pdf"
    pdf_path.write_bytes(b"mock PDF")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "not XML", ""),
    )

    result = read_pdf(pdf_path)

    assert result.record is None
    assert [issue.code for issue in result.issues] == ["invalid_pdf_geometry"]


def test_stage_pdf_photo_converts_one_safe_image_and_returns_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exactly one safe image should become a bounded deterministic JPEG."""
    pdf_path = tmp_path / "003 PESSOA FOTO.pdf"
    pdf_path.write_bytes(b"mock PDF")
    staging = tmp_path / "staging"
    staging.mkdir()
    calls: list[list[str]] = []
    timeouts: list[object] = []
    layout_directories: list[Path] = []
    image_list = """page num type width height color comp bpc enc interp object ID
----------------------------------------------------------------------------
1 0 image 800 800 rgb 3 8 image no 1 0
1 1 smask 800 800 gray 1 8 image no 2 0
"""

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Mock list output and create the extracted image in its requested prefix."""
        calls.append(command)
        timeouts.append(kwargs["timeout"])
        if command[0] == "pdftohtml":
            assert kwargs["timeout"] == PDFTOHTML_TIMEOUT_SECONDS
            layout_directories.append(Path(str(kwargs["cwd"])))
            return subprocess.CompletedProcess(command, 0, _image_layout_xml(), "")
        if command[1] == "-list":
            return subprocess.CompletedProcess(command, 0, image_list, "")
        Image.new("RGB", (800, 800), (40, 80, 120)).save(f"{command[-1]}-000.png")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = stage_pdf_photo(pdf_path, staging, output_name="003.jpg")

    assert result.status == PhotoStageStatus.STAGED
    assert result.manifest is not None
    assert result.manifest.staged_path == staging / "003.jpg"
    assert result.manifest.width == 512
    assert result.manifest.height == 512
    assert result.manifest.sha256 == hashlib.sha256(
        result.manifest.staged_path.read_bytes()
    ).hexdigest()
    assert calls[0] == ["pdfimages", "-list", str(pdf_path)]
    assert calls[1] == [
        "pdftohtml",
        "-xml",
        "-stdout",
        "-hidden",
        str(pdf_path),
    ]
    assert calls[2][:3] == ["pdfimages", "-all", str(pdf_path)]
    assert timeouts == [
        PDFIMAGES_TIMEOUT_SECONDS,
        PDFTOHTML_TIMEOUT_SECONDS,
        PDFIMAGES_TIMEOUT_SECONDS,
    ]
    assert len(layout_directories) == 1
    assert not layout_directories[0].exists()


def test_stage_pdf_photo_rejects_unique_square_logo_outside_profile_region(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A sole square source image should remain ambiguous outside the profile area."""
    pdf_path = tmp_path / "004 PESSOA FOTO.pdf"
    pdf_path.write_bytes(b"mock PDF")
    staging = tmp_path / "staging"
    staging.mkdir()
    image_list = """page num type width height
-------------------------------
1 0 image 800 800
"""
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return a safe source image displayed as a logo elsewhere on the page."""
        calls.append(command)
        if command[0] == "pdfimages":
            return subprocess.CompletedProcess(command, 0, image_list, "")
        return subprocess.CompletedProcess(
            command, 0, _image_layout_xml(((400, 100, 111, 111),)), ""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = stage_pdf_photo(pdf_path, staging)

    assert result.status == PhotoStageStatus.AMBIGUOUS
    assert result.manifest is None
    assert [issue.code for issue in result.issues] == ["photo_layout_ambiguous"]
    assert [command[0] for command in calls] == ["pdfimages", "pdftohtml"]
    assert list(staging.iterdir()) == []


def test_stage_pdf_photo_rejects_multiple_layout_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Multiple displayed images should block extraction even with one source image."""
    pdf_path = tmp_path / "005 PESSOA FOTO.pdf"
    pdf_path.write_bytes(b"mock PDF")
    staging = tmp_path / "staging"
    staging.mkdir()
    image_list = """page num type width height
-------------------------------
1 0 image 800 800
"""

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return one source image but two displayed layout images."""
        if command[0] == "pdfimages":
            return subprocess.CompletedProcess(command, 0, image_list, "")
        return subprocess.CompletedProcess(
            command,
            0,
            _image_layout_xml(((59, 503, 111, 111), (400, 100, 90, 90))),
            "",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = stage_pdf_photo(pdf_path, staging)

    assert result.status == PhotoStageStatus.AMBIGUOUS
    assert [issue.code for issue in result.issues] == ["photo_layout_ambiguous"]
    assert list(staging.iterdir()) == []


def test_stage_pdf_photo_returns_error_for_malformed_layout_xml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Malformed pdftohtml XML should become a stable photo error."""
    pdf_path = tmp_path / "006 PESSOA FOTO.pdf"
    pdf_path.write_bytes(b"mock PDF")
    staging = tmp_path / "staging"
    staging.mkdir()
    image_list = """page num type width height
-------------------------------
1 0 image 800 800
"""

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return a valid image list followed by malformed layout XML."""
        output = image_list if command[0] == "pdfimages" else "<not-closed"
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = stage_pdf_photo(pdf_path, staging)

    assert result.status == PhotoStageStatus.ERROR
    assert result.manifest is None
    assert [issue.code for issue in result.issues] == ["invalid_pdf_image_layout"]
    assert list(staging.iterdir()) == []


def test_stage_pdf_photo_reports_missing_displayed_image(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A source image absent from layout XML should be classified as missing."""
    pdf_path = tmp_path / "007 PESSOA FOTO.pdf"
    pdf_path.write_bytes(b"mock PDF")
    staging = tmp_path / "staging"
    staging.mkdir()
    image_list = """page num type width height
-------------------------------
1 0 image 800 800
"""

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return one source image but no displayed image geometry."""
        output = image_list if command[0] == "pdfimages" else _image_layout_xml(())
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = stage_pdf_photo(pdf_path, staging)

    assert result.status == PhotoStageStatus.MISSING
    assert result.manifest is None
    assert [issue.code for issue in result.issues] == ["photo_layout_missing"]
    assert list(staging.iterdir()) == []


def test_stage_pdf_photo_returns_error_when_pdftohtml_times_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A stalled pdftohtml process should become a stable photo error."""
    pdf_path = tmp_path / "008 PESSOA FOTO.pdf"
    pdf_path.write_bytes(b"mock PDF")
    staging = tmp_path / "staging"
    staging.mkdir()
    image_list = """page num type width height
-------------------------------
1 0 image 800 800
"""

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return a source image and then simulate a layout timeout."""
        if command[0] == "pdfimages":
            return subprocess.CompletedProcess(command, 0, image_list, "")
        timeout = kwargs["timeout"]
        assert isinstance(timeout, (int, float))
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = stage_pdf_photo(pdf_path, staging)

    assert result.status == PhotoStageStatus.ERROR
    assert result.manifest is None
    assert [issue.code for issue in result.issues] == ["pdftohtml_timeout"]
    assert list(staging.iterdir()) == []


def test_stage_pdf_photo_does_not_extract_with_any_extra_non_mask_image(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unsafe extra non-mask image should still make extraction ambiguous."""
    pdf_path = tmp_path / "004 PESSOA FOTO.pdf"
    pdf_path.write_bytes(b"mock PDF")
    staging = tmp_path / "staging"
    staging.mkdir()
    image_list = """page num type width height
-------------------------------
1 0 image 300 300
1 1 image 64 64
"""
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return one safe image and one unsafe extra image."""
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, image_list, "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = stage_pdf_photo(pdf_path, staging)

    assert result.status == PhotoStageStatus.AMBIGUOUS
    assert result.manifest is None
    assert [issue.code for issue in result.issues] == ["photo_ambiguous"]
    assert calls == [["pdfimages", "-list", str(pdf_path)]]
    assert list(staging.iterdir()) == []


@pytest.mark.parametrize(
    ("width", "height"),
    (
        (1200, 300),
        (2480, 3508),
        (1060, 1000),
        (940, 1000),
        (10001, 10000),
        (8000, 8000),
    ),
    ids=(
        "wide-logo",
        "page-scan",
        "aspect-wide",
        "aspect-tall",
        "dimension-limit",
        "pixel-limit",
    ),
)
def test_stage_pdf_photo_rejects_unsafe_image_dimensions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    width: int,
    height: int,
) -> None:
    """Wide, page-sized, and extreme images should not be extracted."""
    pdf_path = tmp_path / "005 PESSOA FOTO.pdf"
    pdf_path.write_bytes(b"mock PDF")
    staging = tmp_path / "staging"
    staging.mkdir()
    image_list = f"""page num type width height
-------------------------------
1 0 image {width} {height}
"""
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return one image whose geometry is unsafe for a profile photo."""
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, image_list, "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = stage_pdf_photo(pdf_path, staging)

    assert result.status == PhotoStageStatus.MISSING
    assert result.manifest is None
    assert [issue.code for issue in result.issues] == ["photo_unsafe"]
    assert calls == [["pdfimages", "-list", str(pdf_path)]]
    assert list(staging.iterdir()) == []
