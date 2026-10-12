"""Pure-stdlib document conversion backends.

The public surface is intentionally small: :func:`extract_pages` for PDF text
and table extraction, plus the Office/OOXML writers added in later stages.
"""

from .pdf import PageContent, PdfEncryptedError, PdfReadError, extract_pages

__all__ = ["extract_pages", "PageContent", "PdfReadError", "PdfEncryptedError"]