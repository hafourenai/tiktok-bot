"""Document conversion with fallback to OCR for scanned pages.

Supports: PDF → DOCX/XLSX/PPTX/Images, Image → PDF, Office → PDF (via LibreOffice).
"""

from .api import (
    SUPPORTED_EXTENSIONS,
    convert_pdf_to_docx,
    convert_pdf_to_xlsx,
    convert_pdf_to_pptx,
    convert_pdf_to_images,
    convert_image_to_pdf,
    convert_office_to_pdf,
)
from .pipeline import new_workspace, cleanup_stale_workspaces, STALE_WORKSPACE_SECONDS

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "convert_pdf_to_docx",
    "convert_pdf_to_xlsx",
    "convert_pdf_to_pptx",
    "convert_pdf_to_images",
    "convert_image_to_pdf",
    "convert_office_to_pdf",
    "new_workspace",
    "cleanup_stale_workspaces",
    "STALE_WORKSPACE_SECONDS",
]
