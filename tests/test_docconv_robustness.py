"""Robustness tests for docconv edge cases and error recovery."""

import pytest
from converter.lib.docconv import extract_pages
from converter.lib.docconv.pdf import PdfReadError
from converter.lib.docconv._page import PdfEncryptedError


class TestMalformedPdfHandling:
    """Test graceful handling of invalid/corrupted PDF inputs."""

    def test_empty_bytes_raises_clear_error(self):
        """Empty input should raise PdfReadError, not obscure exception."""
        with pytest.raises((PdfReadError, ValueError)):
            extract_pages(b"")

    def test_garbage_input_raises_clear_error(self):
        """Non-PDF bytes should raise PdfReadError."""
        with pytest.raises((PdfReadError, ValueError)):
            extract_pages(b"this is not a pdf at all")

    def test_truncated_pdf_fails_cleanly(self):
        """Truncated PDF should not hang or crash."""
        # Create a minimal but incomplete PDF
        incomplete = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog"
        try:
            extract_pages(incomplete)
            pytest.fail("Should have raised an exception")
        except Exception:
            pass  # Any clean failure is acceptable

    def test_corrupted_xref_fails_cleanly(self):
        """Corrupted cross-reference table should fail gracefully."""
        corrupted = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog >> endobj\n"
            b"xref\n"
            b"0 999999\n"  # Claim impossibly many objects
            b"0000000000 65535 f\n"
            b"trailer << /Root 1 0 R /Size 2 >>\n"
        )
        try:
            extract_pages(corrupted)
            pytest.fail("Should have raised an exception")
        except Exception:
            pass

    def test_missing_pages_raises_descriptive_error(self, tmp_path):
        """PDF with /Pages but no page objects should fail clearly."""
        minimal = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n"
            b"xref\n"
            b"0 3\n"
            b"0000000000 65535 f\n"
            b"0000000009 00000 n\n"
            b"0000000074 00000 n\n"
            b"trailer << /Root 1 0 R /Size 3 >>\n"
            b"startxref\n143\n%%EOF\n"
        )
        path = tmp_path / "empty.pdf"
        path.write_bytes(minimal)
        with pytest.raises(PdfReadError, match="halaman"):
            extract_pages(str(path))


class TestImageHandling:
    """Test image codec robustness."""

    def test_truncated_png_raises_clear_error(self):
        """Truncated PNG should raise ImageError."""
        from converter.lib.docconv.imgcodec import ImageError, read_dimensions
        
        png_header = b"\x89PNG\r\n\x1a\n"
        truncated = png_header + b"\x00\x00"
        
        with pytest.raises(ImageError, match="terpotong|tidak"):
            read_dimensions(truncated)

    def test_invalid_image_format_raises_clear_error(self):
        """Unrecognized image format should raise ImageError."""
        from converter.lib.docconv.imgcodec import ImageError, read_dimensions
        
        with pytest.raises(ImageError, match="tidak didukung|Format"):
            read_dimensions(b"NOTAVALIDFORMAT")

    def test_invalid_dimensions_raise_clear_error(self):
        """Invalid dimension values should be handled."""
        from converter.lib.docconv.imgcodec import ImageError, write_png
        
        with pytest.raises(ImageError, match="tidak valid"):
            write_png(-100, 100, b"data")
        
        with pytest.raises(ImageError, match="tidak valid"):
            write_png(100, 0, b"data")


class TestTableDetection:
    """Test table detection does not crash on edge cases."""

    def test_empty_lines_list_returns_empty_tables(self):
        """Empty input should return empty table list, not crash."""
        from converter.lib.docconv.table import detect_tables
        
        tables = detect_tables([])
        assert tables == []

    def test_single_line_returns_empty_tables(self):
        """Single line cannot form a table."""
        from converter.lib.docconv.table import detect_tables
        from converter.lib.docconv._content import LineSegment, Char
        
        char = Char("A", 0, 10, 0, 10, 10)
        line = LineSegment([char])
        
        tables = detect_tables([line])
        assert tables == []


class TestLayoutAnalysis:
    """Test layout analysis robustness."""

    def test_empty_text_runs_handled(self):
        """Empty or whitespace-only text runs should not crash."""
        from converter.lib.docconv.textlayout import build_lines
        from converter.lib.docconv._content import Char
        
        # All whitespace
        chars = [Char(" ", i * 10, (i + 1) * 10, 0, 10, 10) for i in range(3)]
        lines = build_lines(chars, 200)
        
        # Should return lines even if empty
        assert isinstance(lines, list)

    def test_extreme_coordinates_handled(self):
        """Very large or negative coordinates should not crash."""
        from converter.lib.docconv.textlayout import build_lines
        from converter.lib.docconv._content import Char
        
        chars = [
            Char("A", -10000, -9990, 50000, 50010, 10),
            Char("B", 10000000, 10000010, 50000, 50010, 10),
        ]
        lines = build_lines(chars, 200)
        
        # Should handle extreme values gracefully
        assert isinstance(lines, list)


class TestPdfWriter:
    """Test PDF writer error handling."""

    def test_invalid_text_escaping(self, tmp_path):
        """PDF writer should handle invalid characters gracefully."""
        from converter.lib.docconv.pdfwrite import write_text_pdf
        
        path = tmp_path / "out.pdf"
        # Text with control characters and high bytes
        text = "Hello\x00World\xff\xfeTest"
        write_text_pdf([text], str(path))
        
        # Should produce a valid PDF
        assert path.exists()

    def test_very_long_text_wrapping(self, tmp_path):
        """Very long text should wrap without crashing."""
        from converter.lib.docconv.pdfwrite import write_text_pdf
        
        path = tmp_path / "out.pdf"
        long_text = "word " * 1000
        write_text_pdf([long_text], str(path))
        
        # Should produce a valid, potentially multi-page PDF
        assert path.exists()
        assert path.stat().st_size > 0


class TestExcelHelpers:
    """Test Excel/XLSX helper functions."""

    def test_column_index_edge_cases(self):
        """Test column letter conversion edge cases."""
        from converter.lib.docconv.excel import column_to_index, index_to_column
        
        # Round trip various indices
        for idx in [0, 1, 25, 26, 27, 675, 701, 702]:
            letters = index_to_column(idx)
            assert column_to_index(letters) == idx

    def test_invalid_cell_reference_returns_none(self):
        """Invalid cell references should return None gracefully."""
        from converter.lib.docconv.excel import split_ref
        
        assert split_ref("garbage") == (None, None)
        assert split_ref("") == (None, None)
        assert split_ref("1A") == (None, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
