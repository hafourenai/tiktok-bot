"""End-to-end converter tests.

These exercise the public ``converter`` API. Where a document format must be
produced for inspection, the reader from :mod:`docconv` is used, and the raw
package XML is checked directly for the things a reader cannot see (for
example that a cell holding ``=1+1`` is stored as an inline/shared string
rather than a formula).

No third-party document library is required or imported.
"""

import subprocess
import zipfile
from xml.etree import ElementTree

import pytest

import converter
import ocr as ocr_module
from docconv import extract_pages
from docconv.excel import Sheet, write_xlsx
from docconv.imgcodec import save_png
from docconv.pdfwrite import write_text_pdf
from docconv.slides import Slide, write_pptx
from docconv.word import write_docx


def make_png(path, width, height):
    """Write a solid PNG of the given size; used as a stand-in scan."""
    pixels = bytes([200, 210, 220]) * (width * height)
    return save_png(str(path), width, height, pixels, greyscale=False)


def make_pdf(path, pages=((300, 500), (500, 300))):
    """A multipage PDF written by our own writer, one line per page."""
    paragraphs = []
    for index, (text, _size) in enumerate(pages):
        if index:
            paragraphs.append(("", "pagebreak"))
        paragraphs.append(text)
    write_text_pdf(paragraphs, str(path))
    return path


@pytest.fixture
def sample_pdf(tmp_path):
    return make_pdf(tmp_path / "sample.pdf", (
        ("Invoice 123", None),
        ("Second page", None),
    ))


# -- PDF to text formats --------------------------------------------------
def test_pdf_to_docx_round_trip(sample_pdf, tmp_path):
    target = tmp_path / "result.docx"
    converter.convert_pdf_to_docx(str(sample_pdf), str(target))

    from docconv.word import read_docx

    with read_docx(str(target)) as reader:
        text = reader.text()
    assert "Invoice 123" in text
    assert "Second page" in text


def test_pdf_to_docx_preserves_page_break(sample_pdf, tmp_path):
    target = tmp_path / "result.docx"
    converter.convert_pdf_to_docx(str(sample_pdf), str(target))

    with zipfile.ZipFile(target) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    # The page break must be a real w:br, not just a blank paragraph.
    assert 'w:type="page"' in document


def test_pdf_to_xlsx_creates_one_sheet_per_page(sample_pdf, tmp_path):
    target = tmp_path / "result.xlsx"
    converter.convert_pdf_to_xlsx(str(sample_pdf), str(target))

    from docconv.excel import read_xlsx

    with read_xlsx(str(target)) as reader:
        sheets = reader.sheets()
    assert [name for name, _ in sheets] == ["Page 1", "Page 2"]
    assert sheets[0][1][0][0] == "Invoice 123"
    assert sheets[1][1][0][0] == "Second page"


def test_pdf_table_cells_land_in_columns(tmp_path):
    """A real ruled table must map into distinct Excel columns, not one blob.

    Uses the reportlab-generated fixture: our own writer cannot position text
    at explicit coordinates, so it cannot produce a genuine column layout.
    """
    from tests.test_docconv import fixture  # noqa: PLC0415

    source = fixture("table_reportlab.pdf")
    target = tmp_path / "table.xlsx"
    converter.convert_pdf_to_xlsx(source, str(target))

    from docconv.excel import read_xlsx

    with read_xlsx(str(target)) as reader:
        rows = reader.sheets()[0][1]
    assert ["Product", "Qty", "Amount"] in rows
    assert ["Kopi", "2", "30.000"] in rows


def test_formula_like_cells_stay_strings(tmp_path):
    """A PDF cell reading '=1+1' must not become an Excel formula."""
    source = tmp_path / "formula.pdf"
    write_text_pdf(["=1+1", "200"], str(source))
    target = tmp_path / "formula.xlsx"
    converter.convert_pdf_to_xlsx(str(source), str(target))

    with zipfile.ZipFile(target) as archive:
        shared = archive.read("xl/sharedStrings.xml").decode("utf-8")
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    # Cells reference the shared string table (t="s") and carry no <f>.
    assert 't="s"' in sheet
    assert "<f>" not in sheet
    assert "=1+1" in shared


# -- Office to PDF --------------------------------------------------------
@pytest.mark.parametrize("kind", ["docx", "xlsx", "pptx"])
def test_office_fallback_retains_long_text(kind, tmp_path, monkeypatch):
    monkeypatch.setattr(converter, "get_libreoffice_bin", lambda: "")
    source = tmp_path / f"source.{kind}"
    text = "Beginning " + "long content " * 40 + "END_MARKER"

    if kind == "docx":
        write_docx([text], str(source))
    elif kind == "xlsx":
        sheet = Sheet("Data")
        sheet.set(1, 0, text)
        write_xlsx([sheet], str(source))
    else:
        slide = Slide()
        slide.add_text(text)
        write_pptx([slide], str(source))

    target = converter.convert_office_to_pdf(str(source), str(tmp_path / "out"))
    extracted = "\n".join(page.text for page in extract_pages(target))
    # Wrapping inserts newlines, so compare on collapsed whitespace.
    assert "END_MARKER" in extracted.replace("\n", " ")
    assert "Beginning" in extracted


def test_office_fallback_flattens_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(converter, "get_libreoffice_bin", lambda: "")
    source = tmp_path / "table.docx"
    from docconv._ooxml import PackageWriter, content_types_xml
    from docconv.word import DOCUMENT_CONTENT_TYPE

    writer = PackageWriter()
    writer.set("word/document.xml",
               '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<w:document xmlns:w="http://schemas.openxmlformats.org/'
               'wordprocessingml/2006/main"><w:body><w:tbl>'
               '<w:tr><w:tc><w:p><w:r><w:t>Item</w:t></w:r></w:p></w:tc>'
               '<w:tc><w:p><w:r><w:t>2</w:t></w:r></w:p></w:tc></w:tr>'
               "</w:tbl></w:body></w:document>")
    writer.set("_rels/.rels",
               '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/'
               'package/2006/relationships"><Relationship Id="rId1" '
               'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
               'relationships/officeDocument" Target="word/document.xml"/>'
               "</Relationships>")
    writer.write(str(source), content_types_xml(
        [("/word/document.xml", DOCUMENT_CONTENT_TYPE)]))

    target = converter.convert_office_to_pdf(str(source), str(tmp_path))
    extracted = "\n".join(page.text for page in extract_pages(target))
    assert "Item | 2" in extracted


def test_libreoffice_failure_uses_fallback(tmp_path, monkeypatch):
    source = tmp_path / "input.docx"
    write_docx(["Fallback reached"], str(source))
    monkeypatch.setattr(converter, "get_libreoffice_bin", lambda: "soffice")

    def run(cmd, **kwargs):
        assert any(arg.startswith("-env:UserInstallation=file:") for arg in cmd)
        raise subprocess.TimeoutExpired(cmd, 120)

    monkeypatch.setattr(converter.subprocess, "run", run)
    # A stale file must not be mistaken for LibreOffice output.
    (tmp_path / "input.pdf").write_bytes(b"stale output")
    target = converter.convert_office_to_pdf(str(source), str(tmp_path))
    assert "Fallback reached" in extract_pages(target)[0].text


def test_libreoffice_success_is_preferred(tmp_path, monkeypatch):
    source = tmp_path / "input.docx"
    write_docx(["Hello"], str(source))
    monkeypatch.setattr(converter, "get_libreoffice_bin", lambda: "soffice")

    def run(cmd, **kwargs):
        outdir = cmd[cmd.index("--outdir") + 1]
        write_text_pdf(["from libreoffice"], f"{outdir}/input.pdf")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(converter.subprocess, "run", run)
    target = converter.convert_office_to_pdf(str(source), str(tmp_path))
    assert "from libreoffice" in extract_pages(target)[0].text


def test_empty_office_document_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(converter, "get_libreoffice_bin", lambda: "")
    source = tmp_path / "empty.docx"
    write_docx([], str(source))
    with pytest.raises(RuntimeError, match="tidak memiliki teks"):
        converter.convert_office_to_pdf(str(source), str(tmp_path))


# -- images ---------------------------------------------------------------
@pytest.fixture
def sample_png(tmp_path):
    return make_png(tmp_path / "image.png", 60, 40)


def test_image_to_pdf_produces_matching_page_size(sample_png, tmp_path):
    target = tmp_path / "image.pdf"
    converter.convert_image_to_pdf(str(sample_png), str(target))
    page = extract_pages(target)[0]
    # 100 DPI: 60px -> 43.2pt, 40px -> 28.8pt.
    assert page.width == pytest.approx(43.2, rel=1e-3)
    assert page.height == pytest.approx(28.8, rel=1e-3)


def test_unsupported_image_is_rejected(tmp_path):
    bogus = tmp_path / "nope.bmp"
    bogus.write_bytes(b"BM" + b"\x00" * 64)
    with pytest.raises(RuntimeError, match="tidak didukung"):
        converter.convert_image_to_pdf(str(bogus), str(tmp_path / "out.pdf"))


# -- rendering (poppler) --------------------------------------------------
def test_missing_poppler_reports_how_to_install(tmp_path):
    monkey = pytest.MonkeyPatch()
    monkey.setattr(converter, "get_poppler_bin", lambda: "")
    try:
        with pytest.raises(RuntimeError, match="pdftoppm"):
            converter.convert_pdf_to_images(str(make_pdf(tmp_path / "a.pdf")),
                                            str(tmp_path))
    finally:
        monkey.undo()


def test_poppler_render_is_ordered_and_png(tmp_path, monkeypatch):
    """Drive _render_pdf through a stub pdftoppm so the test needs no binary."""
    source = make_pdf(tmp_path / "three.pdf", (("a", None), ("b", None), ("c", None)))
    output = tmp_path / "render"

    def fake_run(cmd, **kwargs):
        # Emulate pdftoppm: zero-padded names written out of order.
        prefix = cmd[-1]
        for number in (2, 1, 3):
            Path = __import__("pathlib").Path
            (Path(prefix).parent / f"page-{number}.png").write_bytes(b"x")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(converter, "get_poppler_bin", lambda: "pdftoppm")
    monkeypatch.setattr(converter.subprocess, "run", fake_run)
    paths = converter.convert_pdf_to_images(str(source), str(output))
    assert [p.rsplit("-", 1)[-1] for p in paths] == ["1.png", "2.png", "3.png"]


def test_poppler_failure_is_reported(tmp_path, monkeypatch):
    source = make_pdf(tmp_path / "a.pdf")
    monkeypatch.setattr(converter, "get_poppler_bin", lambda: "pdftoppm")
    monkeypatch.setattr(converter.subprocess, "run", lambda cmd, **kw:
                        subprocess.CompletedProcess(cmd, 1, b"", b"boom"))
    with pytest.raises(RuntimeError, match="pdftoppm gagal"):
        converter.convert_pdf_to_images(str(source), str(tmp_path / "out"))


def test_pdf_to_pptx_preserves_aspect_ratio(tmp_path, monkeypatch):
    source = make_pdf(tmp_path / "wide.pdf", (("page", None),))

    def fake_render(input_path, output_dir, dpi=150):
        import pathlib

        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        # A 400x200 image is 2:1.
        return [make_png(pathlib.Path(output_dir) / "page-1.png", 400, 200)]

    monkeypatch.setattr(converter, "_render_pdf", fake_render)
    target = tmp_path / "slides.pptx"
    converter.convert_pdf_to_pptx(str(source), str(target))

    from docconv.slides import read_pptx

    with read_pptx(str(target)) as reader:
        slides = reader.slides()
    assert len(slides) == 1
    left, top, width, height = slides[0].pictures[0]
    assert left >= 0 and top >= 0
    assert left + width <= 9144000
    assert top + height <= 5143500
    assert width / height == pytest.approx(2.0, rel=1e-3)


# -- OCR ------------------------------------------------------------------
def test_scan_without_text_is_rejected(tmp_path, monkeypatch):
    sample_png = make_png(tmp_path / "scan.png", 20, 20)
    pdf = tmp_path / "scan.pdf"
    converter.convert_image_to_pdf(sample_png, str(pdf))

    monkeypatch.setattr(ocr_module, "get_tesseract_bin", lambda: "")
    monkeypatch.setattr(converter, "_render_pdf", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("no poppler")))
    with pytest.raises(RuntimeError, match="tesseract-ocr"):
        converter.convert_pdf_to_docx(str(pdf), str(tmp_path / "scan.docx"))


def test_ocr_text_reaches_the_docx(tmp_path, monkeypatch):
    sample_png = make_png(tmp_path / "scan.png", 20, 20)
    pdf = tmp_path / "scan.pdf"
    converter.convert_image_to_pdf(sample_png, str(pdf))

    def fake_render(input_path, output_dir, dpi=150):
        import pathlib

        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        return [make_png(pathlib.Path(output_dir) / "page-1.png", 20, 20)]

    monkeypatch.setattr(converter, "_render_pdf", fake_render)
    monkeypatch.setattr(ocr_module, "image_to_text",
                        lambda image, langs=None: "HASIL_OCR_BERHASIL")

    target = tmp_path / "scan.docx"
    converter.convert_pdf_to_docx(str(pdf), str(target))
    from docconv.word import read_docx

    with read_docx(str(target)) as reader:
        assert "HASIL_OCR_BERHASIL" in reader.text()


def test_ocr_language_falls_back_to_english(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_module, "get_tesseract_bin", lambda: "/bin/tesseract")
    monkeypatch.setattr(ocr_module, "available_languages", lambda: ["eng"])
    assert ocr_module._resolve_langs("/bin/tesseract", "ind+eng") == "eng"


def test_ocr_reports_missing_language_pack(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_module, "get_tesseract_bin", lambda: "/bin/tesseract")
    monkeypatch.setattr(ocr_module, "available_languages", lambda: ["fra"])
    with pytest.raises(ocr_module.OCRUnavailable, match="language pack"):
        ocr_module._resolve_langs("/bin/tesseract", "ind+eng")


def test_ocr_missing_binary_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_module, "get_tesseract_bin", lambda: "")
    with pytest.raises(ocr_module.OCRUnavailable, match="tesseract"):
        ocr_module.image_to_text(str(tmp_path / "nope.png"))


def test_supported_extensions_are_unchanged():
    assert converter.SUPPORTED_EXTENSIONS[".pdf"] == [
        "docx", "xlsx", "pptx", "images"]
    assert converter.SUPPORTED_EXTENSIONS[".docx"] == ["pdf"]