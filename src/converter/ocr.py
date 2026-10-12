"""OCR wrapper with retry logic and better error handling.

Handles scanned PDFs when direct text extraction fails.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_OCR_LANGS = os.environ.get("OCR_LANGS", "ind+eng")
OCR_TIMEOUT = 120
OCR_MAX_RETRIES = 2


class OCRUnavailable(RuntimeError):
    """Raised when OCR cannot be performed."""
    pass


class OCRError(RuntimeError):
    """Raised when OCR processing fails."""
    pass


def get_tesseract_bin() -> str:
    """Locate tesseract binary in standard paths."""
    candidates = [
        os.environ.get("TESSERACT_BIN", ""),
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\Aldi Nova\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/data/data/com.termux/files/usr/bin/tesseract",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def is_ocr_available() -> bool:
    """Check if tesseract is available and functional."""
    binary = get_tesseract_bin()
    if not binary:
        return False
    try:
        result = subprocess.run([binary, "--version"], 
                              capture_output=True, timeout=10)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def available_languages() -> list:
    """Get list of installed language packs."""
    binary = get_tesseract_bin()
    if not binary:
        return []
    try:
        result = subprocess.run([binary, "--list-langs"], 
                              capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    lines = (result.stdout or b"").decode("utf-8", "replace").splitlines()
    return [line.strip() for line in lines[1:] if line.strip()]


def _resolve_langs(binary: str, langs: str) -> str:
    """Resolve requested languages to available ones."""
    installed = set(available_languages())
    if not installed:
        return langs
    
    wanted = [part for part in langs.split("+") if part]
    usable = [part for part in wanted if part in installed]
    
    if usable:
        return "+".join(usable)
    if "eng" in installed:
        logger.warning("Language pack '%s' tidak ditemukan; fallback ke 'eng'", langs)
        return "eng"
    
    raise OCRUnavailable(
        f"Tesseract language pack '{langs}' tidak tersedia. "
        f"Tersedia: {', '.join(sorted(installed)) or 'tidak ada'}."
    )


def image_to_text(image_path: str, langs: str | None = None) -> str:
    """Extract text from image using OCR with retry logic.
    
    Args:
        image_path: Path to PNG/JPEG/TIFF image
        langs: Language codes separated by + (default: OCR_LANGS env var)
    
    Returns:
        Extracted text
    
    Raises:
        OCRUnavailable: If tesseract is not available
        OCRError: If OCR processing fails after retries
    """
    binary = get_tesseract_bin()
    if not binary:
        raise OCRUnavailable(
            "Tesseract OCR tidak ditemukan di sistem. "
            "Pasang tesseract binary + language pack 'ind' dan 'eng'."
        )
    
    path = Path(str(image_path))
    if not path.is_file():
        raise OCRUnavailable(f"Berkas gambar tidak ditemukan: {path}")
    
    languages = _resolve_langs(binary, langs or DEFAULT_OCR_LANGS)
    cmd = [binary, str(path), "stdout", "-l", languages]
    
    last_error = None
    for attempt in range(OCR_MAX_RETRIES):
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=OCR_TIMEOUT)
            if result.returncode == 0:
                text = (result.stdout or b"").decode("utf-8", "replace").strip()
                if text:
                    if attempt > 0:
                        logger.info("OCR berhasil pada attempt %d/%d", attempt + 1, OCR_MAX_RETRIES)
                    return text
                # Tesseract succeeded but no text extracted
                raise OCRError("Tesseract tidak menemukan teks di gambar")
            
            detail = (result.stderr or b"").decode("utf-8", "replace").strip()
            raise OCRError(f"Tesseract gagal (kode {result.returncode}): {detail}")
            
        except subprocess.TimeoutExpired:
            last_error = OCRError(f"Tesseract melewati batas waktu {OCR_TIMEOUT}s")
            if attempt < OCR_MAX_RETRIES - 1:
                logger.warning("OCR timeout pada attempt %d, retry...", attempt + 1)
                continue
        except (OSError, OCRError) as e:
            last_error = e
            if attempt < OCR_MAX_RETRIES - 1:
                logger.warning("OCR gagal pada attempt %d, retry... (%s)", attempt + 1, str(e))
                continue
    
    raise last_error or OCRError("OCR gagal setelah semua retry")
