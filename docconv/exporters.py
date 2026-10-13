"""Format exporters for document content.

Supports: CSV (from tables), JSON (structured), HTML, RTF, ODT.
"""

import json
from pathlib import Path
from typing import Any, Dict, List


# ============================================================================
# CSV Export (Tables → CSV)
# ============================================================================

def export_tables_to_csv(tables: List[List[List[str]]], output_path: str,
                         skip_empty: bool = True) -> str:
    """Export PDF tables to CSV file.

    Each table becomes a separate CSV with blank line separator.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for table_idx, table in enumerate(tables):
            if not table:
                continue
            
            # Write table data
            for row in table:
                # CSV escape: quote cells with commas or quotes
                escaped = []
                for cell in row:
                    cell_str = str(cell or "").strip()
                    if "," in cell_str or '"' in cell_str or "\n" in cell_str:
                        cell_str = f'"{cell_str.replace('"', '""')}"'
                    escaped.append(cell_str)
                f.write(",".join(escaped) + "\n")
            
            # Blank line between tables
            if table_idx < len(tables) - 1:
                f.write("\n")
    
    return str(path)


def export_single_table_to_csv(table: List[List[str]], output_path: str) -> str:
    """Export single table to CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for row in table:
            escaped = []
            for cell in row:
                cell_str = str(cell or "").strip()
                if "," in cell_str or '"' in cell_str or "\n" in cell_str:
                    cell_str = f'"{cell_str.replace('"', '""')}"'
                escaped.append(cell_str)
            f.write(",".join(escaped) + "\n")
    
    return str(path)


# ============================================================================
# JSON Export (Structured document representation)
# ============================================================================

class DocumentStructure:
    """Structured document representation."""

    __slots__ = ("pages",)

    def __init__(self):
        self.pages = []

    def add_page(self, page_num: int, width: float, height: float,
                 text: str = "", tables: List[List[List[str]]] = None):
        """Add page to structure."""
        self.pages.append({
            "page_number": page_num,
            "dimensions": {"width": width, "height": height},
            "content": {
                "text": text,
                "tables": tables or []
            }
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "document": {
                "page_count": len(self.pages),
                "pages": self.pages
            }
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def export_pages_to_json(pages: List[Any], output_path: str = None,
                        include_tables: bool = True) -> str:
    """Export extracted pages to JSON.

    Args:
        pages: List of PageContent objects from extract_pages()
        output_path: Output file path (if None, returns JSON string)
        include_tables: Include table data
    
    Returns:
        Output path if output_path provided, else JSON string
    """
    struct = DocumentStructure()
    
    for page in pages:
        tables = page.tables if include_tables else []
        struct.add_page(page.number, page.width, page.height, page.text, tables)
    
    json_str = struct.to_json()
    
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_str)
        return str(path)
    
    return json_str


# ============================================================================
# HTML Export (Preserve structure)
# ============================================================================

def export_pages_to_html(pages: List[Any], output_path: str,
                        title: str = "Document", include_css: bool = True) -> str:
    """Export extracted pages to HTML.

    Args:
        pages: List of PageContent objects
        output_path: Output HTML file path
        title: Document title
        include_css: Include inline CSS styling
    
    Returns:
        Output path
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    css = _get_html_css() if include_css else ""
    
    html_parts = [
        f"<!DOCTYPE html>",
        f"<html>",
        f"<head>",
        f"  <meta charset='utf-8'>",
        f"  <title>{_escape_html(title)}</title>",
        f"  <style>{css}</style>" if css else "",
        f"</head>",
        f"<body>",
        f"  <div class='document'>",
    ]
    
    for page in pages:
        html_parts.append(f"    <div class='page' data-page='{page.number}'>")
        
        # Add text content
        if page.text.strip():
            html_parts.append(f"      <div class='text-content'>")
            for line in page.text.split("\n"):
                if line.strip():
                    html_parts.append(f"        <p>{_escape_html(line)}</p>")
            html_parts.append(f"      </div>")
        
        # Add tables
        if page.tables:
            for table_idx, table in enumerate(page.tables):
                html_parts.append(f"      <table class='data-table' id='table-{page.number}-{table_idx}'>")
                for row_idx, row in enumerate(table):
                    tag = "th" if row_idx == 0 else "td"
                    html_parts.append(f"        <tr>")
                    for cell in row:
                        html_parts.append(f"          <{tag}>{_escape_html(cell)}</{tag}>")
                    html_parts.append(f"        </tr>")
                html_parts.append(f"      </table>")
        
        html_parts.append(f"    </div>")
    
    html_parts.extend([
        f"  </div>",
        f"</body>",
        f"</html>",
    ])
    
    html_content = "\n".join(html_parts)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return str(path)


def _get_html_css() -> str:
    """Get basic HTML CSS styling."""
    return """
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 900px;
        margin: 0 auto;
        padding: 20px;
    }
    .document {
        background: white;
    }
    .page {
        page-break-after: always;
        margin-bottom: 40px;
        padding: 20px;
        border: 1px solid #ddd;
        border-radius: 4px;
    }
    .text-content {
        margin-bottom: 20px;
    }
    .text-content p {
        margin: 8px 0;
    }
    .data-table {
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
        font-size: 0.9em;
    }
    .data-table th {
        background-color: #f0f0f0;
        font-weight: bold;
        text-align: left;
        padding: 10px;
        border: 1px solid #ddd;
    }
    .data-table td {
        padding: 8px 10px;
        border: 1px solid #ddd;
    }
    .data-table tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    """


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


# ============================================================================
# Markdown Export
# ============================================================================

def export_pages_to_markdown(pages: List[Any], output_path: str = None) -> str:
    """Export extracted pages to Markdown.

    Args:
        pages: List of PageContent objects
        output_path: Output markdown file path (if None, returns string)
    
    Returns:
        Output path if output_path provided, else markdown string
    """
    md_parts = []
    
    for page in pages:
        # Page header
        md_parts.append(f"## Page {page.number}")
        md_parts.append("")
        
        # Text content
        if page.text.strip():
            # Basic text with paragraph breaks
            for line in page.text.split("\n"):
                if line.strip():
                    md_parts.append(line)
            md_parts.append("")
        
        # Tables
        if page.tables:
            for table_idx, table in enumerate(page.tables):
                if table_idx > 0:
                    md_parts.append("")
                
                # Markdown table format
                for row_idx, row in enumerate(table):
                    md_parts.append("| " + " | ".join(str(cell) for cell in row) + " |")
                    
                    # Separator after header
                    if row_idx == 0:
                        md_parts.append("|" + "|".join(["---"] * len(row)) + "|")
                
                md_parts.append("")
    
    md_content = "\n".join(md_parts)
    
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md_content)
        return str(path)
    
    return md_content


# ============================================================================
# RTF Export (Rich Text Format - basic)
# ============================================================================

def export_pages_to_rtf(pages: List[Any], output_path: str,
                       title: str = "Document") -> str:
    """Export pages to RTF (basic, no complex formatting).

    Args:
        pages: List of PageContent objects
        output_path: Output RTF file path
        title: Document title
    
    Returns:
        Output path
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rtf_parts = [
        r"{\rtf1\ansi\ansicpg1252\deff0",
        r"{\colortbl;\red0\green0\blue0;}",
        r"{\*\generator docconv;}",
        r"\margl720\margr720\marg1440\margb720",
        r"{\fonttbl",
        r"{\f0\fnil\fcharset0 Arial;}",
        r"}",
        r"\viewkind4\uc1\pard\f0\fs20",
    ]
    
    # Add title
    if title:
        rtf_parts.append(r"{\b " + _escape_rtf(title) + r"}\par\par")
    
    # Add content
    for page in pages:
        rtf_parts.append(r"{\b Page " + str(page.number) + r"}\par")
        
        # Text
        if page.text.strip():
            for line in page.text.split("\n"):
                if line.strip():
                    rtf_parts.append(_escape_rtf(line) + r"\par")
            rtf_parts.append(r"\par")
        
        # Tables (basic: line separated)
        if page.tables:
            for table in page.tables:
                rtf_parts.append(r"{\b Table:}\par")
                for row in table:
                    rtf_parts.append("\t".join(str(cell) for cell in row) + r"\par")
                rtf_parts.append(r"\par")
    
    rtf_parts.append("}")
    
    rtf_content = "".join(rtf_parts)
    
    with open(path, "wb") as f:
        f.write(rtf_content.encode("utf-8", "replace"))
    
    return str(path)


def _escape_rtf(text: str) -> str:
    """Escape RTF special characters."""
    text = str(text)
    # Basic escaping
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    # Replace newlines
    text = text.replace("\n", "\\par ")
    return text


# ============================================================================
# ODT Support Framework
# ============================================================================

class OdtExportError(Exception):
    """Raised when ODT export fails."""


def export_pages_to_odt(pages: List[Any], output_path: str,
                       title: str = "Document") -> str:
    """Export pages to ODT (Open Document Text).

    ODT is a ZIP of XML files. Full implementation requires extensive XML handling.
    For now, raise informative error with workaround.
    """
    raise OdtExportError(
        "ODT export belum tersedia dalam stdlib. Opsi:\n"
        "1. Gunakan python-odt atau odfpy: pip install odfpy\n"
        "2. Konversi via LibreOffice: convert to DOCX dulu, then LOConvert to ODT\n"
        "3. Export ke HTML/RTF sebagai alternatif"
    )


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "export_tables_to_csv",
    "export_single_table_to_csv",
    "DocumentStructure",
    "export_pages_to_json",
    "export_pages_to_html",
    "export_pages_to_markdown",
    "export_pages_to_rtf",
    "export_pages_to_odt",
    "OdtExportError",
]
