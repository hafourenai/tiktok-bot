from pathlib import Path
from types import SimpleNamespace

import pytest

from src.converter.compress import compress_pdf


def test_compression_presets_and_output(tmp_path, monkeypatch):
    source = tmp_path / "in.pdf"
    source.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
    output = tmp_path / "out.pdf"
    monkeypatch.setattr("src.converter.compress.shutil.which", lambda name: "/usr/bin/gs")

    def run(command, **kwargs):
        assert "-dPDFSETTINGS=/ebook" in command
        assert "-dSAFER" in command
        output.write_bytes(b"%PDF-1.4\n")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("src.converter.compress.subprocess.run", run)
    before, after = compress_pdf(str(source), str(output))
    assert before > after


def test_invalid_pdf_rejected_before_process(tmp_path, monkeypatch):
    source = tmp_path / "in.pdf"
    source.write_bytes(b"not a pdf")
    monkeypatch.setattr("src.converter.compress.shutil.which", lambda name: "/usr/bin/gs")
    with pytest.raises(ValueError, match="bukan PDF"):
        compress_pdf(str(source), str(tmp_path / "out.pdf"))


def test_missing_ghostscript(tmp_path, monkeypatch):
    monkeypatch.delenv("GHOSTSCRIPT_BIN", raising=False)
    monkeypatch.setattr("src.converter.compress.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="pkg install ghostscript"):
        compress_pdf(str(tmp_path / "in.pdf"), str(tmp_path / "out.pdf"))
