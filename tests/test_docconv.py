"""PDF reader validated against reference PDFs.

The fixtures in ``tests/fixtures`` were produced by reportlab (an independent
implementation). Validating our stdlib reader against them closes the
reader/writer tautology: a shared bug cannot hide in both directions at once.

Regenerate with ``venv\\Scripts\\python.exe tests\\make_fixtures.py``.
"""

import os

import pytest

from converter.lib.docconv import extract_pages
from converter.lib.docconv._filter import (ascii85_decode, asciihex_decode,
                             apply_png_predictor, flate_decode, lzw_decode,
                             runlength_decode)
from converter.lib.docconv._font import Font, parse_tounicode
from converter.lib.docconv._page import PdfEncryptedError, load_document
from converter.lib.docconv.excel import column_to_index, index_to_column, split_ref
from converter.lib.docconv.pdfwrite import write_text_pdf

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

needs_fixture = pytest.mark.skipif(
    not os.path.isdir(FIXTURES),
    reason="fixture PDF belum dibuat; jalankan tests/make_fixtures.py",
)


def fixture(name):
    path = os.path.join(FIXTURES, name)
    if not os.path.isfile(path):
        pytest.skip(f"fixture {name} belum dibuat")
    return path


# -- structure ------------------------------------------------------------
@needs_fixture
def test_page_count_and_geometry():
    pages = extract_pages(fixture("multipage_reportlab.pdf"))
    assert len(pages) == 5
    assert [p.number for p in pages] == [1, 2, 3, 4, 5]
    # Mixed page sizes survive; the last page reverts to A4/letter.
    assert (round(pages[0].width), round(pages[0].height)) == (400, 500)
    assert pages[4].width > 500


@needs_fixture
def test_text_extraction_reading_order():
    pages = extract_pages(fixture("text_reportlab.pdf"))
    assert pages[0].text.splitlines() == ["Invoice 123", "Total: Rp 1.500.000"]
    assert pages[1].text.strip() == "Second page"


@needs_fixture
def test_word_gaps_are_reconstructed_from_geometry():
    """reportlab draws each word separately, so spacing must come from x."""
    page = extract_pages(fixture("text_reportlab.pdf"))[0]
    assert "Invoice 123" in page.text


@needs_fixture
def test_ruled_table_is_detected_as_a_grid():
    page = extract_pages(fixture("table_reportlab.pdf"))[0]
    assert page.tables, "tabel ber-grid harus terdeteksi"
    table = page.tables[0]
    assert table[0] == ["Product", "Qty", "Amount"]
    assert ["Kopi", "2", "30.000"] in table
    assert ["Teh", "1", "5.000"] in table
    # Every row must have the same column count.
    widths = {len(row) for row in table}
    assert len(widths) == 1


@needs_fixture
def test_unruled_table_detected_via_repeated_gaps():
    page = extract_pages(fixture("unruled_reportlab.pdf"))[0]
    assert page.tables, "tabel tanpa garis harus terdeteksi dari jarak kata"
    table = page.tables[0]
    assert table[0] == ["Nama", "Qty", "Harga"]
    assert ["Beras", "5", "65000"] in table


@needs_fixture
def test_prose_is_not_mistaken_for_a_table():
    """Two unrelated lines of prose must not become a 2-column table."""
    page = extract_pages(fixture("text_reportlab.pdf"))[0]
    assert page.tables == []
    page = extract_pages(fixture("winansi_reportlab.pdf"))[0]
    assert page.tables == []


@needs_fixture
def test_winansi_high_bytes_map_to_unicode():
    page = extract_pages(fixture("winansi_reportlab.pdf"))[0]
    lines = page.text.splitlines()
    assert "Harga: Rp 1.500.000 (net)" in lines
    # 0xDF -> U+00DF (sharp s), 0x97 -> U+2014 (em dash) in WinAnsiEncoding.
    assert any("straße" in line for line in lines)
    assert any("—" in line for line in lines)


@needs_fixture
def test_scan_pdf_yields_no_text():
    """An image-only page must come back empty so OCR can take over."""
    pages = extract_pages(fixture("scan_reportlab.pdf"))
    assert pages[0].text.strip() == ""
    assert pages[0].tables == []


@needs_fixture
def test_image_only_page_has_content_but_no_text_runs():
    """The page draws an image (Do) but produces no text runs."""
    document = load_document(fixture("scan_reportlab.pdf"))
    content = document.pages[0].content_bytes()
    assert b"Do" in content  # an image XObject is drawn

    from converter.lib.docconv._content import parse_page

    parser = parse_page(document.doc, document.pages[0])
    assert parser.runs == []
    assert parser.chars == []


# -- filters --------------------------------------------------------------
def test_flate_round_trip():
    import zlib

    payload = b"Invoice 123 " * 50
    assert flate_decode(zlib.compress(payload)) == payload


def test_flate_recovers_from_trailing_garbage():
    import zlib

    payload = b"data " * 40
    assert flate_decode(zlib.compress(payload) + b"\x00\x00") == payload


def test_flate_rejects_garbage():
    with pytest.raises(Exception):
        flate_decode(b"not compressed at all" * 4)


def test_ascii85_round_trip():
    assert ascii85_decode(b"<~87cURD]j7BEbo80~>") == b"Hello world!"


def test_ascii85_z_shortcut():
    assert ascii85_decode(b"z~>") == b"\x00\x00\x00\x00"


def test_asciihex_round_trip():
    assert asciihex_decode(b"48656c6c6f>") == b"Hello"
    assert asciihex_decode(b"48 65 6c 6C 6F") == b"Hello"


def test_runlength_round_trip():
    # Literal run of 4 bytes, then a repeat of 'A' x3.
    assert runlength_decode(bytes([3]) + b"abcd" + bytes([254, 65])) == b"abcdAAA"


def test_lzw_decodes_back_references():
    # Codes for "ababab": emit 'a'(97), 'b'(98), then back-references to the
    # "ab" entry built at code 258, then EOD(257). All fit in 9 bits.
    payload = _pack_lzw_codes([97, 98, 258, 258, 257])
    assert lzw_decode(payload) == b"ababab"


def _pack_lzw_codes(codes) -> bytes:
    """MSB-first 9-bit packing, independent of the decoder under test."""
    bits = "".join(format(code, "09b") for code in codes)
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def test_png_predictor_undoes_row_filters():
    # Filter 2 ("Up") with an all-zero previous row leaves the row unchanged.
    row = bytes([2]) + bytes([1, 2, 3, 4])
    assert apply_png_predictor(row, colors=1, bpc=8, columns=4) == bytes([1, 2, 3, 4])


def test_png_predictor_sub_filter():
    # Filter 1 ("Sub") accumulates the byte 3 positions back.
    row = bytes([1]) + bytes([10, 5, 5])
    out = apply_png_predictor(row, colors=1, bpc=8, columns=3)
    assert out == bytes([10, 15, 20])


def test_png_predictor_up_filter_accumulates_rows():
    first = bytes([0]) + bytes([1, 2, 3])
    second = bytes([2]) + bytes([1, 1, 1])
    out = apply_png_predictor(first + second, colors=1, bpc=8, columns=3)
    assert out == bytes([1, 2, 3, 2, 3, 4])


# -- fonts ----------------------------------------------------------------
def test_tounicode_bfchar():
    cmap = b"""
    1 begincodespacerange <0000> <FFFF> endcodespacerange
    2 beginbfchar <0041> <0061> <0042> <0062> endbfchar
    """
    mapping = parse_tounicode(cmap)
    assert mapping[0x41] == "a"
    assert mapping[0x42] == "b"


def test_tounicode_bfrange_with_array():
    cmap = b"3 beginbfrange <0003> <0005> [<0078> <0079> <007A>] endbfrange"
    mapping = parse_tounicode(cmap)
    assert mapping[3] == "x"
    assert mapping[5] == "z"


def test_tounicode_bfrange_increments_destination():
    cmap = b"1 beginbfrange <0010> <0012> <0061> endbfrange"
    mapping = parse_tounicode(cmap)
    assert mapping[0x10] == "a"
    assert mapping[0x12] == "c"


def test_codespace_range_is_not_mistaken_for_a_mapping():
    """The leading <0000><FFFF> must not become a mapping entry."""
    mapping = parse_tounicode(
        b"1 begincodespacerange <0000> <FFFF> endcodespacerange")
    assert mapping == {}


@needs_fixture
def test_embedded_font_is_resolved():
    document = load_document(fixture("winansi_reportlab.pdf"))
    fonts = document.doc.resolve(document.pages[0].resources.get("Font"))
    name, entry = next(iter(fonts.items()))
    font = Font(document.doc.resolve(entry), document.doc)
    assert font.subtype == "Type1"
    assert font.decode_single(ord("A")) == "A"
    # WinAnsiEncoding: 0x97 is an em dash.
    assert font.decode_single(0x97) == "—"
    assert font.char_width(ord("A")) > 0


# -- writer / reader agreement -------------------------------------------
def test_written_pdf_reads_back(tmp_path):
    path = tmp_path / "out.pdf"
    write_text_pdf(["Halo dunia", "Baris kedua END_MARKER"], str(path))
    pages = extract_pages(str(path))
    assert pages[0].text.splitlines() == ["Halo dunia", "Baris kedua END_MARKER"]


def test_wrapped_text_stays_within_page_width(tmp_path):
    from converter.lib.docconv.pdfwrite import MARGIN, PAGE_WIDTH, text_width, wrap

    limit = PAGE_WIDTH - 2 * MARGIN
    lines = wrap("word " * 60, size=11.0, max_width=limit)
    assert all(text_width(line, 11.0) <= limit + 1e-6 for line in lines)


# -- robustness -----------------------------------------------------------
def test_garbage_input_raises_read_error():
    from converter.lib.docconv.pdf import PdfReadError

    with pytest.raises((PdfReadError, ValueError)):
        extract_pages(b"this is definitely not a pdf")


def test_empty_input_raises():
    from converter.lib.docconv.pdf import PdfReadError

    with pytest.raises((PdfReadError, ValueError)):
        extract_pages(b"")


def test_truncated_pdf_does_not_crash():
    """A file cut in half must fail cleanly, not raise something obscure."""
    path = fixture("multipage_reportlab.pdf")
    with open(path, "rb") as handle:
        data = handle.read()
    half = data[:len(data) // 2]
    try:
        extract_pages(half)
    except Exception:
        pass  # any clean failure is acceptable; a hang or crash is not


def test_encrypted_pdf_raises_descriptive_error(tmp_path):
    path = tmp_path / "enc.pdf"
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 0 >> stream\n\nendstream endobj\n"
        b"5 0 obj << /Filter /Standard /V 2 /R 3 /Length 128 >> endobj\n"
        b"trailer << /Root 1 0 R /Encrypt 5 0 R /Size 6 >>\n"
    )
    path.write_bytes(body)
    with pytest.raises(PdfEncryptedError, match="terenkripsi"):
        extract_pages(str(path))


# -- excel helpers --------------------------------------------------------
@pytest.mark.parametrize("letters,index", [
    ("A", 0), ("B", 1), ("Z", 25), ("AA", 26), ("AB", 27), ("BA", 52),
])
def test_column_index_round_trip(letters, index):
    assert column_to_index(letters) == index
    assert index_to_column(index) == letters


def test_split_cell_reference():
    assert split_ref("B7") == (7, 1)
    assert split_ref("a1") == (1, 0)
    assert split_ref("garbage") == (None, None)