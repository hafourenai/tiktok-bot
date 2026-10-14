"""OCR via the tesseract CLI.

Tesseract itself cannot be reimplemented (it is a trained model), but the
Python wrapper around it is unnecessary: the CLI reads an image file and prints
text on stdout. Passing a file path also keeps the pipeline free of Pillow,
since ``pdftoppm`` already writes PNGs we can hand straight to tesseract.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_OCR_LANGS = os.environ.get("OCR_LANGS", "ind+eng")
OCR_TIMEOUT = 120


class OCRUnavailable(RuntimeError):
    """Raised when the tesseract binary or language data is missing."""
    pass


def get_tesseract_bin() -> str:
    """Look for the tesseract executable in standard paths and PATH."""
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
    """True when the tesseract binary can be invoked."""
    return bool(get_tesseract_bin())


def available_languages() -> list:
    """Language packs installed alongside the binary."""
    binary = get_tesseract_bin()
    if not binary:
        return []
    try:
        result = subprocess.run([binary, "--list-langs"], capture_output=True,
                                timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    lines = (result.stdout or b"").decode("utf-8", "replace").splitlines()
    return [line.strip() for line in lines[1:] if line.strip()]


def _resolve_langs(binary: str, langs: str) -> str:
    """Drop language packs tesseract does not have installed."""
    installed = set(available_languages())
    if not installed:
        return langs
    wanted = [part for part in langs.split("+") if part]
    usable = [part for part in wanted if part in installed]
    if usable:
        return "+".join(usable)
    if "eng" in installed:
        logger.warning("Language pack untuk %s tidak ditemukan; memakai 'eng'", langs)
        return "eng"
    raise OCRUnavailable(
        f"Tesseract tidak memiliki language pack untuk '{langs}'. "
        f"Tersedia: {', '.join(sorted(installed)) or 'tidak ada'}."
    )


def image_to_text(image, langs: str | None = None) -> str:
    """OCR an image file (or an already-open file path) to text.

    ``image`` is a path to a PNG/JPEG/TIFF file. It stays path-shaped for
    backwards compatibility with callers that pass a filename.
    """
    binary = get_tesseract_bin()
    if not binary:
        raise OCRUnavailable(
            "Tesseract OCR tidak ditemukan di sistem. Pasang binary tesseract "
            "beserta language pack 'ind' (Bahasa Indonesia) dan 'eng'."
        )
    path = Path(str(image))
    if not path.is_file():
        raise OCRUnavailable(f"Berkas gambar tidak ditemukan: {path}")

    languages = _resolve_langs(binary, langs or DEFAULT_OCR_LANGS)
    cmd = [binary, str(path), "stdout", "-l", languages]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=OCR_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise OCRUnavailable(f"Tesseract melewati batas waktu {OCR_TIMEOUT}s.") from exc
    except OSError as exc:
        raise OCRUnavailable(f"Gagal menjalankan tesseract: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise OCRUnavailable(f"Tesseract gagal (kode {result.returncode}): {detail}")
    return (result.stdout or b"").decode("utf-8", "replace").strip()