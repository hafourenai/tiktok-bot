import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from pdf2docx import Converter
import docx
import openpyxl
from pptx import Presentation
import fitz  # PyMuPDF
from PIL import Image

SUPPORTED_EXTENSIONS = {
    ".pdf": ["docx", "xlsx", "pptx", "images"],
    ".docx": ["pdf"],
    ".xlsx": ["pdf"],
    ".pptx": ["pdf"],
    ".jpg": ["pdf"],
    ".jpeg": ["pdf"],
    ".png": ["pdf"],
}

LIBREOFFICE_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    shutil.which("soffice") or "",
    shutil.which("libreoffice") or "",
]


def get_libreoffice_bin() -> str:
    for p in LIBREOFFICE_PATHS:
        if p and os.path.exists(p):
            return p
    return ""


def convert_pdf_to_docx(input_path: str, output_path: str) -> str:
    cv = Converter(input_path)
    cv.convert(output_path, start=0, end=None)
    cv.close()
    return output_path


def convert_pdf_to_xlsx(input_path: str, output_path: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Extracted"
    doc = fitz.open(input_path)
    current_row = 1
    for page in doc:
        tabs = page.find_tables()
        if tabs.tables:
            for table in tabs.tables:
                for row in table.extract():
                    for col_idx, val in enumerate(row, 1):
                        ws.cell(row=current_row, column=col_idx, value=val)
                    current_row += 1
                current_row += 1
        else:
            # Fallback text lines if no tables detected
            lines = page.get_text("text").splitlines()
            for line in lines:
                if line.strip():
                    ws.cell(row=current_row, column=1, value=line.strip())
                    current_row += 1
            current_row += 1
    wb.save(output_path)
    return output_path


def convert_pdf_to_pptx(input_path: str, output_path: str) -> str:
    prs = Presentation()
    # Set 16:9 widescreen or default
    prs.slide_width = fitz.paper_size("a4")[1] * 72 * 10
    doc = fitz.open(input_path)
    blank_slide_layout = prs.slide_layouts[6]

    with tempfile.TemporaryDirectory() as tmp_dir:
        for idx, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_path = os.path.join(tmp_dir, f"page_{idx}.png")
            pix.save(img_path)
            slide = prs.slides.add_slide(blank_slide_layout)
            slide.shapes.add_picture(img_path, 0, 0, width=prs.slide_width)
    prs.save(output_path)
    return output_path


def convert_pdf_to_images(input_path: str, output_dir: str) -> list[str]:
    doc = fitz.open(input_path)
    image_paths = []
    for idx, page in enumerate(doc):
        pix = page.get_pixmap(dpi=200)
        img_path = os.path.join(output_dir, f"page_{idx + 1}.png")
        pix.save(img_path)
        image_paths.append(img_path)
    return image_paths


def convert_image_to_pdf(input_path: str, output_path: str) -> str:
    img = Image.open(input_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(output_path, "PDF", resolution=100.0)
    return output_path


def convert_office_to_pdf(input_path: str, output_dir: str) -> str:
    """Uses LibreOffice headless or fallback python engines."""
    lo_bin = get_libreoffice_bin()
    if lo_bin:
        cmd = [lo_bin, "--headless", "--convert-to", "pdf", "--outdir", output_dir, input_path]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        base_name = Path(input_path).stem + ".pdf"
        out_file = os.path.join(output_dir, base_name)
        if os.path.exists(out_file):
            return out_file

    ext = Path(input_path).suffix.lower()
    if ext == ".docx":
        # Reportlab / python-docx fallback text to PDF
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        out_file = os.path.join(output_dir, Path(input_path).stem + ".pdf")
        doc = docx.Document(input_path)
        c = canvas.Canvas(out_file, pagesize=letter)
        y = 750
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                c.drawString(50, y, text[:90])
                y -= 20
                if y < 50:
                    c.showPage()
                    y = 750
        c.save()
        return out_file
    elif ext == ".xlsx":
        wb = openpyxl.load_workbook(input_path, data_only=True)
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        out_file = os.path.join(output_dir, Path(input_path).stem + ".pdf")
        c = canvas.Canvas(out_file, pagesize=letter)
        y = 750
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            c.drawString(50, y, f"--- Sheet: {sheet} ---")
            y -= 25
            for row in ws.iter_rows(values_only=True):
                line = " | ".join(str(v) for v in row if v is not None)
                if line.strip():
                    c.drawString(50, y, line[:85])
                    y -= 18
                    if y < 50:
                        c.showPage()
                        y = 750
        c.save()
        return out_file
    else:
        raise RuntimeError("LibreOffice tidak ditemukan untuk convert format ini.")
