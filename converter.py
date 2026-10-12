"""Document conversion built on the stdlib-only :mod:`docconv` package.

Rendering (PDF to image/PPT) needs the poppler ``pdftoppm`` binary and Office
to PDF prefers LibreOffice; both are external binaries detected at call time.
Text extraction and all Office read/write paths have no third-party dependency.
"""

import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf": ["docx", "xlsx", "pptx", "images"],
    ".docx": ["pdf"], ".xlsx": ["pdf"], ".pptx": ["pdf"],
    ".jpg": ["pdf"], ".jpeg": ["pdf"], ".png": ["pdf"],
}

# Every conversion runs inside a workspace of its own so that a crashed or
# interrupted run can be identified and removed later without touching temp
# files belonging to other processes.
WORKSPACE_NAME = "bot_honey_converter"
# Only sweep workspaces older than this. A second bot instance sharing the same
# system temp directory may have a conversion in flight right now; its
# workspace is recent, so it is left alone.
STALE_WORKSPACE_SECONDS = 3600


def get_workspace() -> Path:
    """Root directory holding one subdirectory per conversion run."""
    return Path(tempfile.gettempdir()) / WORKSPACE_NAME


def new_workspace(prefix: str = "run-") -> str:
    """Create a fresh workspace directory for one conversion."""
    workspace = get_workspace()
    workspace.mkdir(parents=True, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=str(workspace))


def cleanup_stale_workspaces(max_age: int = STALE_WORKSPACE_SECONDS) -> list:
    """Delete leftover conversion workspaces from earlier crashed runs.

    Only directories inside :func:`get_workspace` are considered, and only
    those older than ``max_age`` seconds, so this is safe to call at startup
    even when another instance is converting concurrently.
    """
    workspace = get_workspace()
    if not workspace.is_dir():
        return []
    removed = []
    cutoff = time.time() - max_age
    for entry in sorted(workspace.iterdir()):
        try:
            if not entry.is_dir():
                continue
            if entry.stat().st_mtime >= cutoff:
                continue
            shutil.rmtree(entry, ignore_errors=True)
            if entry.exists():
                continue
            removed.append(entry.name)
        except OSError:
            # A workspace that is locked (Windows) is not fatal at startup;
            # the next run will try again.
            continue
    if removed:
        logger.info("Membersihkan %d workspace konversi sisa: %s",
                    len(removed), ", ".join(removed[:5]))
    return removed


def get_libreoffice_bin() -> str:
    candidates = [
        os.environ.get("LIBREOFFICE_BIN", ""),
        shutil.which("soffice"), shutil.which("libreoffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    return next((p for p in candidates if p and Path(p).is_file()), "")


def get_poppler_bin() -> str:
    """Locate pdftoppm from poppler, used only for PDF rasterisation.

    Text extraction never needs this; PDF to PPT/images does.
    """
    candidates = [
        os.environ.get("POPPLER_BIN", ""),
        shutil.which("pdftoppm"),
        r"C:\Program Files\poppler\Library\bin\pdftoppm.exe",
        r"C:\Program Files\poppler\bin\pdftoppm.exe",
        "/usr/bin/pdftoppm", "/usr/local/bin/pdftoppm",
        "/data/data/com.termux/files/usr/bin/pdftoppm",
    ]
    return next((p for p in candidates if p and Path(p).is_file()), "")


POPPLER_MISSING = (
    "Render PDF membutuhkan pdftoppm dari poppler.\n"
    "Windows: unduh zip Release dari oschwartz10612/poppler-windows, ekstrak, lalu "
    "tambahkan folder bin-nya ke PATH atau set POPPLER_BIN.\n"
    "Termux: pkg install poppler.\n"
    "Ekstraksi teks PDF tetap berjalan tanpa poppler."
)


def _pdf_pages(input_path):
    """Return text and tables per page. Automatically performs OCR on scanned pages."""
    from docconv.pdf import PdfReadError, extract_pages

    try:
        extracted = extract_pages(input_path)
    except PdfReadError as exc:
        raise RuntimeError(str(exc)) from exc
    pages = [(page.text, page.tables) for page in extracted]
    if not pages:
        raise RuntimeError("PDF tidak memiliki halaman.")

    # Check if any page is scanned / contains no extractable text
    needs_ocr = [idx for idx, (text, tables) in enumerate(pages) if not text.strip() and not tables]
    if needs_ocr:
        try:
            import ocr
            rendered_images = _render_pdf(input_path, tempfile.mkdtemp(), dpi=200)
            try:
                for idx in needs_ocr:
                    if idx < len(rendered_images):
                        ocr_text = ocr.image_to_text(rendered_images[idx])
                        if ocr_text:
                            _, tables = pages[idx]
                            pages[idx] = (ocr_text, tables)
            finally:
                # Cleanup temporary rendered images
                if rendered_images:
                    shutil.rmtree(os.path.dirname(rendered_images[0]), ignore_errors=True)
        except Exception as ocr_err:
            logger.info("OCR tidak berhasil dijalankan: %s", ocr_err)

    if any(not text.strip() and not tables for text, tables in pages):
        raise RuntimeError(
            "PDF memiliki halaman tanpa teks yang dapat diekstrak (scan/gambar atau kosong). "
            "Pastikan tesseract-ocr terpasang untuk OCR otomatis; PPT/gambar tetap dapat digunakan."
        )
    return pages


def convert_pdf_to_docx(input_path: str, output_path: str) -> str:
    from docconv.word import write_docx

    paragraphs = []
    for index, (text, _tables) in enumerate(_pdf_pages(input_path)):
        if index:
            paragraphs.append(("", "pagebreak"))
        for line in text.splitlines():
            paragraphs.append(line)
    write_docx(paragraphs, output_path)
    return output_path


def convert_pdf_to_xlsx(input_path: str, output_path: str) -> str:
    from docconv.excel import Sheet, write_xlsx

    sheets = []
    for index, (text, tables) in enumerate(_pdf_pages(input_path), 1):
        sheet = Sheet(f"Page {index}")
        if tables:
            row_index = 1
            for table in tables:
                for row in table:
                    for column, value in enumerate(row):
                        if value is not None and str(value).strip():
                            sheet.set(row_index, column, value)
                    row_index += 1
                row_index += 1  # blank separator between tables
        else:
            for row_index, line in enumerate(text.splitlines(), 1):
                if line.strip():
                    sheet.set(row_index, 0, line)
        sheets.append(sheet)
    write_xlsx(sheets, output_path)
    return output_path


def _render_pdf(input_path, output_dir, dpi=150):
    """Rasterise every page to PNG using the poppler CLI (pdftoppm)."""
    binary = get_poppler_bin()
    if not binary:
        raise RuntimeError(POPPLER_MISSING)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"
    cmd = [binary, "-png", "-r", str(int(dpi)), str(input_path), str(prefix)]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Gagal menjalankan pdftoppm: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"pdftoppm gagal (kode {result.returncode}): {detail}")
    # pdftoppm names files page-1.png, page-2.png, ... (zero-padded when the
    # page count is large), so sort numerically rather than lexically.
    produced = sorted(output_dir.glob("page-*.png"),
                      key=lambda p: _page_sort_key(p.stem))
    if not produced:
        raise RuntimeError("pdftoppm tidak menghasilkan gambar.")
    return [str(path) for path in produced]


def _page_sort_key(stem: str):
    suffix = stem.rsplit("-", 1)[-1]
    return (0, int(suffix)) if suffix.isdigit() else (1, 0)


def convert_pdf_to_pptx(input_path: str, output_path: str) -> str:
    from docconv.imgcodec import read_dimensions_file
    from docconv.slides import Slide, write_pptx

    with tempfile.TemporaryDirectory() as tmp:
        paths = _render_pdf(input_path, tmp)
        slide_width = 9144000
        first_w, first_h = read_dimensions_file(paths[0])
        slide_height = max(914400, min(51206400,
                                       round(slide_width * first_h / first_w)))
        slides, pictures = [], []
        for path in paths:
            width, height = read_dimensions_file(path)
            scale = min(slide_width / width, slide_height / height)
            w, h = max(1, round(width * scale)), max(1, round(height * scale))
            left, top = (slide_width - w) // 2, (slide_height - h) // 2
            slide = Slide()
            slide.add_picture(left, top, w, h)
            slides.append(slide)
            pictures.append([path])
        write_pptx(slides, output_path, slide_width, slide_height, pictures)
    return output_path


def convert_pdf_to_images(input_path: str, output_dir: str) -> list[str]:
    return _render_pdf(input_path, output_dir, dpi=200)


def convert_image_to_pdf(input_path: str, output_path: str) -> str:
    from docconv.imgcodec import ImageError, image_to_pdf

    try:
        return image_to_pdf(input_path, output_path, dpi=100.0)
    except ImageError as exc:
        raise RuntimeError(str(exc)) from exc


def _office_text_pdf(input_path, output_path):
    """Portable text-only fallback with wrapping and pagination."""
    from docconv.pdfwrite import write_text_pdf

    story = []

    def add(text):
        if str(text).strip():
            story.append(str(text))

    def break_page(text=""):
        story.append((text, True))

    ext = Path(input_path).suffix.lower()
    if ext == ".docx":
        from docconv.word import read_docx

        with read_docx(input_path) as reader:
            for kind, value in reader.iter_blocks():
                if kind == "paragraph":
                    add(value)
                else:
                    for row in value:
                        add(" | ".join(cell for cell in row))
    elif ext == ".xlsx":
        from docconv.excel import read_xlsx

        with read_xlsx(input_path) as reader:
            for index, (title, rows) in enumerate(reader.sheets()):
                if index:
                    break_page()
                add(title)
                for row in rows:
                    if any(value for value in row):
                        add(" | ".join(value for value in row))
    elif ext == ".pptx":
        from docconv.slides import read_pptx

        with read_pptx(input_path) as reader:
            for index, slide in enumerate(reader.slides()):
                if index:
                    break_page()
                for text in slide.texts:
                    add(text)
    else:
        raise RuntimeError(f"Format Office {ext} belum didukung.")
    if not any(isinstance(item, str) and item.strip() for item in story):
        raise RuntimeError("Dokumen tidak memiliki teks. Pasang LibreOffice untuk merender gambar/layout.")
    write_text_pdf(story, output_path)
    return output_path


def convert_office_to_pdf(input_path: str, output_dir: str) -> str:
    input_path = str(Path(input_path).resolve())
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = str(Path(output_dir) / (Path(input_path).stem + ".pdf"))
    lo_bin = get_libreoffice_bin()
    if lo_bin:
        with tempfile.TemporaryDirectory() as tmp:
            profile = (Path(tmp) / "profile").as_uri()
            cmd = [lo_bin, f"-env:UserInstallation={profile}", "--headless",
                   "--convert-to", "pdf", "--outdir", tmp, input_path]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=120)
                result = Path(tmp) / (Path(input_path).stem + ".pdf")
                if result.is_file() and result.stat().st_size:
                    shutil.copyfile(result, output_path)
                    return output_path
                logger.warning("LibreOffice tidak menghasilkan PDF; menggunakan fallback teks")
            except (OSError, subprocess.SubprocessError):
                logger.warning("LibreOffice gagal; menggunakan fallback teks", exc_info=True)
    return _office_text_pdf(input_path, output_path)
