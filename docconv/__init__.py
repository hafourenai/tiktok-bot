"""Pure-stdlib document conversion library.

Provides PDF text/table extraction and OOXML format writers (DOCX/XLSX/PPTX).
"""

from .pdf import PageContent, PdfEncryptedError, PdfReadError, extract_pages

__all__ = ["extract_pages", "PageContent", "PdfReadError", "PdfEncryptedError"]