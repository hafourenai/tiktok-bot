"""Run with the same Python used to start bot.py; never prints tokens."""
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parent
    failed = False
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    for module, package in [
        ("telegram", "python-telegram-bot"), ("yt_dlp", "yt-dlp"),
        ("dotenv", "python-dotenv"), ("gallery_dl", "gallery-dl"),
        ("discord", "discord.py"), ("PIL", "Pillow"), ("tzdata", "tzdata"),
    ]:
        try:
            importlib.import_module(module)
            print(f"OK: {package}")
        except Exception as error:
            failed = True
            print(f"GAGAL: {package} ({type(error).__name__}: {error})")
    # Document conversion is stdlib-only; these external binaries are optional
    # and only gate specific paths, so report them without failing the check.
    sys.path.insert(0, str(root))
    try:
        from converter.lib.docconv.pdf import extract_pages

        print("OK: converter (konversi dokumen, tanpa library pihak ketiga)")
        del extract_pages
    except Exception as error:
        failed = True
        print(f"GAGAL: converter ({type(error).__name__}: {error})")
    for label, module_name, finder in [
        ("LibreOffice (Word/Excel/PPT ke PDF)", "converter.api", "get_libreoffice_bin"),
        ("poppler/pdftoppm (PDF ke gambar/PPT)", "converter.api", "get_poppler_bin"),
        ("tesseract (OCR halaman scan)", "converter.ocr", "get_tesseract_bin"),
    ]:
        try:
            module = importlib.import_module(module_name)
            available = bool(getattr(module, finder)())
        except Exception:
            available = False
        print(f"{'OK' if available else 'OPSIONAL (tidak ada)'}: {label}")
    for executable in ("node", "ffmpeg"):
        available = shutil.which(executable)
        failed |= not bool(available)
        print(f"{'OK' if available else 'GAGAL'}: {executable}")
    if shutil.which("node"):
        result = subprocess.run(
            ["node", "-e", "require('@tobyg74/tiktok-api-dl')"], cwd=root,
            capture_output=True, timeout=30,
        )
        failed |= result.returncode != 0
        print(f"{'OK' if result.returncode == 0 else 'GAGAL'}: @tobyg74/tiktok-api-dl (npm install)")
        result = subprocess.run(
            ["node", "-e", "require('instagram-private-api')"], cwd=root,
            capture_output=True, timeout=30,
        )
        print(f"{'OK' if result.returncode == 0 else 'OPSIONAL (tidak ada)'}: instagram-private-api (npm install)")
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
    except ImportError:
        pass
    for name, default in [("DOWNLOAD_DIR", "downloads"),
                          ("VOICE_DATABASE_PATH", "data/voice_stats.db"),
                          ("VOICE_EXPORT_DIR", "data/exports")]:
        path = Path(os.getenv(name, default)).expanduser()
        if not path.is_absolute():
            path = root / path
        if name == "VOICE_DATABASE_PATH":
            path = path.parent
        try:
            path.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=path) as probe:
                probe.write(b"storage-check")
                probe.flush()
            print(f"OK: {name}, tulis file berhasil; kosong {shutil.disk_usage(path).free // (1024 * 1024)} MB")
        except OSError as error:
            failed = True
            print(f"GAGAL: {name} ({type(error).__name__}: {error})")
    if failed:
        print("Perbaiki bagian GAGAL. Dependency Python: python -m pip install -r requirements.txt")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
