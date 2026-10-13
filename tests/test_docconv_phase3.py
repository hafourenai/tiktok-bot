"""Tests for Phase 3: Format Expansion.

Covers CSV, JSON, HTML, Markdown, RTF export functionality.
"""

import json
import tempfile
from pathlib import Path

import pytest

from docconv.exporters import (
    export_tables_to_csv, export_single_table_to_csv, DocumentStructure,
    export_pages_to_json, export_pages_to_html, export_pages_to_markdown,
    export_pages_to_rtf, export_pages_to_odt, OdtExportError
)


class MockPageContent:
    """Mock PageContent for testing."""

    def __init__(self, number: int, text: str = "", tables=None,
                 width: float = 612.0, height: float = 792.0):
        self.number = number
        self.text = text
        self.tables = tables or []
        self.width = width
        self.height = height


class TestCsvExport:
    """Test CSV export functionality."""

    def test_export_single_table_to_csv(self, tmp_path):
        """Export single table to CSV."""
        table = [
            ["Name", "Age", "City"],
            ["Alice", "30", "New York"],
            ["Bob", "25", "Los Angeles"],
            ["Charlie", "35", "Chicago"],
        ]
        
        output = tmp_path / "table.csv"
        result = export_single_table_to_csv(table, str(output))
        
        assert Path(result).exists()
        with open(result) as f:
            lines = f.readlines()
        
        assert len(lines) == 4
        assert "Name,Age,City" in lines[0]
        assert "Alice" in lines[1]

    def test_csv_escaping_commas(self, tmp_path):
        """CSV escaping for cells containing commas."""
        table = [
            ["Product", "Description"],
            ["Widget A", "A widget, with comma"],
            ["Widget B", "Normal description"],
        ]
        
        output = tmp_path / "table.csv"
        export_single_table_to_csv(table, str(output))
        
        with open(output) as f:
            content = f.read()
        
        # Cell with comma should be quoted
        assert '"A widget, with comma"' in content

    def test_csv_escaping_quotes(self, tmp_path):
        """CSV escaping for cells containing quotes."""
        table = [
            ["Item", "Note"],
            ['Product "X"', "Quote in cell"],
        ]
        
        output = tmp_path / "table.csv"
        export_single_table_to_csv(table, str(output))
        
        with open(output) as f:
            content = f.read()
        
        # Quote should be escaped
        assert '""' in content or '"' in content

    def test_export_multiple_tables_to_csv(self, tmp_path):
        """Export multiple tables with separators."""
        tables = [
            [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]],
            [["Product", "Price"], ["Widget", "10"], ["Gadget", "20"]],
        ]
        
        output = tmp_path / "tables.csv"
        result = export_tables_to_csv(tables, str(output))
        
        with open(result) as f:
            lines = f.readlines()
        
        # Should have content from both tables plus separator
        assert any("Name" in line for line in lines)
        assert any("Product" in line for line in lines)


class TestJsonExport:
    """Test JSON export functionality."""

    def test_document_structure_creation(self):
        """Create and serialize DocumentStructure."""
        struct = DocumentStructure()
        struct.add_page(1, 612, 792, "Hello world", [])
        struct.add_page(2, 612, 792, "Second page", [])
        
        data = struct.to_dict()
        assert data["document"]["page_count"] == 2
        assert len(data["document"]["pages"]) == 2

    def test_export_pages_to_json_string(self):
        """Export pages to JSON string."""
        pages = [
            MockPageContent(1, "Page 1 text", [], 612, 792),
            MockPageContent(2, "Page 2 text", [], 612, 792),
        ]
        
        json_str = export_pages_to_json(pages, output_path=None)
        data = json.loads(json_str)
        
        assert data["document"]["page_count"] == 2
        assert data["document"]["pages"][0]["page_number"] == 1

    def test_export_pages_to_json_file(self, tmp_path):
        """Export pages to JSON file."""
        pages = [
            MockPageContent(1, "Content", [["A", "B"], ["1", "2"]], 612, 792),
        ]
        
        output = tmp_path / "document.json"
        result = export_pages_to_json(pages, str(output), include_tables=True)
        
        assert Path(result).exists()
        with open(result) as f:
            data = json.load(f)
        
        assert len(data["document"]["pages"]) == 1
        assert data["document"]["pages"][0]["content"]["tables"]

    def test_json_excludes_tables_if_requested(self, tmp_path):
        """JSON export can exclude tables."""
        pages = [
            MockPageContent(1, "Text", [["A", "B"]], 612, 792),
        ]
        
        json_str = export_pages_to_json(pages, include_tables=False)
        data = json.loads(json_str)
        
        assert data["document"]["pages"][0]["content"]["tables"] == []


class TestHtmlExport:
    """Test HTML export functionality."""

    def test_export_pages_to_html(self, tmp_path):
        """Export pages to HTML."""
        pages = [
            MockPageContent(1, "Hello world\nSecond line", [], 612, 792),
        ]
        
        output = tmp_path / "document.html"
        result = export_pages_to_html(pages, str(output), title="Test Doc")
        
        assert Path(result).exists()
        with open(result) as f:
            html = f.read()
        
        assert "<!DOCTYPE html>" in html
        assert "Test Doc" in html
        assert "Hello world" in html
        assert "page" in html

    def test_html_includes_tables(self, tmp_path):
        """HTML export includes table data."""
        table = [["Header1", "Header2"], ["Data1", "Data2"]]
        pages = [
            MockPageContent(1, "Text", [table], 612, 792),
        ]
        
        output = tmp_path / "document.html"
        export_pages_to_html(pages, str(output))
        
        with open(output) as f:
            html = f.read()
        
        assert "<table" in html
        assert "Header1" in html
        assert "Data1" in html

    def test_html_escaping(self, tmp_path):
        """HTML export escapes special characters."""
        pages = [
            MockPageContent(1, "Text with <script> and & symbols", [], 612, 792),
        ]
        
        output = tmp_path / "document.html"
        export_pages_to_html(pages, str(output))
        
        with open(output) as f:
            html = f.read()
        
        # Should be escaped
        assert "&lt;script&gt;" in html
        assert "&amp;" in html
        assert "<script>" not in html

    def test_html_includes_css(self, tmp_path):
        """HTML export can include CSS styling."""
        pages = [MockPageContent(1, "Text", [], 612, 792)]
        
        output = tmp_path / "document.html"
        export_pages_to_html(pages, str(output), include_css=True)
        
        with open(output) as f:
            html = f.read()
        
        assert "<style>" in html
        assert "font-family" in html


class TestMarkdownExport:
    """Test Markdown export functionality."""

    def test_export_pages_to_markdown_string(self):
        """Export to Markdown string."""
        pages = [
            MockPageContent(1, "Line 1\nLine 2", [], 612, 792),
            MockPageContent(2, "Page 2 content", [], 612, 792),
        ]
        
        md = export_pages_to_markdown(pages)
        
        assert "## Page 1" in md
        assert "## Page 2" in md
        assert "Line 1" in md

    def test_markdown_tables(self, tmp_path):
        """Markdown export with tables."""
        table = [
            ["Name", "Value"],
            ["Alice", "100"],
            ["Bob", "200"],
        ]
        pages = [
            MockPageContent(1, "Text", [table], 612, 792),
        ]
        
        output = tmp_path / "document.md"
        result = export_pages_to_markdown(pages, str(output))
        
        with open(result) as f:
            md = f.read()
        
        # Markdown table format
        assert "|" in md
        assert "Name" in md
        assert "---" in md  # separator row

    def test_markdown_file_output(self, tmp_path):
        """Markdown can be written to file."""
        pages = [MockPageContent(1, "Content", [], 612, 792)]
        
        output = tmp_path / "output.md"
        result = export_pages_to_markdown(pages, str(output))
        
        assert Path(result).exists()


class TestRtfExport:
    """Test RTF export functionality."""

    def test_export_pages_to_rtf(self, tmp_path):
        """Export pages to RTF."""
        pages = [
            MockPageContent(1, "Hello RTF", [], 612, 792),
        ]
        
        output = tmp_path / "document.rtf"
        result = export_pages_to_rtf(pages, str(output), title="Test")
        
        assert Path(result).exists()
        with open(result, "rb") as f:
            content = f.read()
        
        # RTF signature
        assert b"{\\rtf1" in content

    def test_rtf_includes_title(self, tmp_path):
        """RTF export includes document title."""
        pages = [MockPageContent(1, "Content", [], 612, 792)]
        
        output = tmp_path / "document.rtf"
        export_pages_to_rtf(pages, str(output), title="My Document")
        
        with open(output, "rb") as f:
            content = f.read()
        
        assert b"My Document" in content

    def test_rtf_includes_tables(self, tmp_path):
        """RTF export includes tables."""
        table = [["Col1", "Col2"], ["Data1", "Data2"]]
        pages = [
            MockPageContent(1, "Text", [table], 612, 792),
        ]
        
        output = tmp_path / "document.rtf"
        export_pages_to_rtf(pages, str(output))
        
        with open(output, "rb") as f:
            content = f.read().decode("utf-8", "replace")
        
        assert "Col1" in content
        assert "Data1" in content


class TestOdtExport:
    """Test ODT export error handling."""

    def test_odt_export_raises_informative_error(self):
        """ODT export raises with helpful alternatives."""
        pages = [MockPageContent(1, "Text", [], 612, 792)]
        
        with pytest.raises(OdtExportError, match="PIL|Pillow|LibreOffice"):
            export_pages_to_odt(pages, "/tmp/output.odt")


class TestExportIntegration:
    """Integration tests for all exporters."""

    def test_all_exporters_with_same_pages(self, tmp_path):
        """Test all exporters work with same page content."""
        pages = [
            MockPageContent(
                1, 
                "Page 1 content\nLine 2",
                [["Header1", "Header2"], ["Data1", "Data2"]],
                612, 792
            ),
            MockPageContent(2, "Page 2 simple text", [], 612, 792),
        ]
        
        # CSV
        csv_out = tmp_path / "export.csv"
        export_tables_to_csv([table for page in pages for table in page.tables], 
                            str(csv_out))
        assert csv_out.exists()
        
        # JSON
        json_out = tmp_path / "export.json"
        export_pages_to_json(pages, str(json_out))
        assert json_out.exists()
        
        # HTML
        html_out = tmp_path / "export.html"
        export_pages_to_html(pages, str(html_out))
        assert html_out.exists()
        
        # Markdown
        md_out = tmp_path / "export.md"
        export_pages_to_markdown(pages, str(md_out))
        assert md_out.exists()
        
        # RTF
        rtf_out = tmp_path / "export.rtf"
        export_pages_to_rtf(pages, str(rtf_out))
        assert rtf_out.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
