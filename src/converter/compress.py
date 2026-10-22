"""Local PDF compression using Ghostscript."""

import os
import shutil
import subprocess
from pathlib import Path


PDF_PRESETS = {
    "light": "/printer",
    "medium": "/ebook",
    "high": "/screen",
}


def compress_pdf(input_path: str, output_path: str, level: str = "medium") -> tuple[int, int]:
    """Return (original bytes, compressed bytes). Output remains in the caller's workspace."""
    if level not in PDF_PRESETS:
        raise ValueError("Tingkat kompresi PDF tidak dikenal.")
    binary = os.environ.get("GHOSTSCRIPT_BIN") or shutil.which("gs") or shutil.which("gswin64c")
    if not binary:
        raise RuntimeError("Ghostscript belum terpasang. Di Termux jalankan: pkg install ghostscript")
    source = Path(input_path)
    output = Path(output_path)
    if source.resolve() == output.resolve():
        raise ValueError("File input dan output harus berbeda.")
    with source.open("rb") as file:
        if file.read(5) != b"%PDF-":
            raise ValueError("File yang dikirim bukan PDF yang valid.")
    command = [
        binary, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={PDF_PRESETS[level]}", "-dNOPAUSE", "-dBATCH", "-dSAFER",
        "-dQUIET", f"-sOutputFile={output}", str(source),
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as error:
        output.unlink(missing_ok=True)
        raise RuntimeError("Kompresi PDF melewati batas waktu 3 menit.") from error
    if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise RuntimeError("Ghostscript gagal memproses PDF (mungkin rusak atau dilindungi sandi).")
    with output.open("rb") as file:
        if file.read(5) != b"%PDF-":
            output.unlink(missing_ok=True)
            raise RuntimeError("Hasil kompresi bukan PDF yang valid.")
    return source.stat().st_size, output.stat().st_size
