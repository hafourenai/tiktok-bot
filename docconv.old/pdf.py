"""Public PDF text and table extraction API."""

import logging

from ._content import parse_page
from ._page import PdfEncryptedError, load_document
from .textlayout import build_lines, reading_order_text
from .table import detect_tables

logger = logging.getLogger(__name__)


class PdfReadError(RuntimeError):
    """Raised when a PDF cannot be read at all."""


class PageContent:
    """Extracted content of a single page."""

    __slots__ = ("text", "tables", "number", "width", "height")

    def __init__(self, text: str, tables: list, number: int = 1,
                 width: float = 0.0, height: float = 0.0):
        self.text = text
        self.tables = tables
        self.number = number
        self.width = width
        self.height = height

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<PageContent {self.number}: {len(self.text)} chars, {len(self.tables)} tables>"


def extract_pages(source) -> list:
    """Extract text and tables from every page of a PDF.

    ``source`` is a path or raw bytes. Raises :class:`PdfReadError` when the
    file is not a readable PDF and :class:`PdfEncryptedError` when encrypted.
    """
    document = load_document(source)
    if not document.pages:
        raise PdfReadError("PDF tidak memiliki halaman.")
    pages = []
    for page in document.pages:
        parser = parse_page(document.doc, page)
        try:
            lines = build_lines(parser.chars, page.width)
            tables = detect_tables(lines, parser.lines, parser.rects, page.width)
            text = reading_order_text(lines)
        except Exception:
            logger.warning("Gagal menyusun tata letak halaman %s", page.number,
                           exc_info=True)
            text = "\n".join(run.text for run in parser.runs if run.text.strip())
            tables = []
        for warning in _font_warnings(parser):
            logger.debug("Halaman %s: %s", page.number, warning)
        pages.append(PageContent(text, tables, page.number, page.width, page.height))
    return pages


def _font_warnings(parser):
    seen = []
    for run in parser.runs:
        font = run.font
        if font is not None and font.warnings:
            for warning in font.warnings:
                if warning not in seen:
                    seen.append(warning)
    return seen


__all__ = ["extract_pages", "PageContent", "PdfReadError", "PdfEncryptedError"]