"""Rebuild editable PDF text and ruled tables into a formatted Word document.

Usage: python scripts/pdf_to_formatted_docx.py input.pdf output.docx
Requires pdfplumber and python-docx.
"""

import re
import sys

import pdfplumber
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches, Pt


def add_text(doc, page, top, bottom, page_number):
    if bottom - top < 2:
        return
    region = page.crop((0, top, page.width, bottom))
    lines = [(line["text"].strip(), line["top"], line["bottom"])
             for line in region.extract_text_lines(x_tolerance=2, y_tolerance=3)
             if line["text"].strip()]
    paragraph = []
    previous_bottom = None
    bullet = False

    def flush():
        nonlocal bullet
        if paragraph:
            text = " ".join(paragraph)
            doc.add_paragraph(text, style="List Bullet" if bullet else None)
            paragraph.clear()
        bullet = False

    for line, y, end in lines:
        if previous_bottom is not None and y - previous_bottom > 14:
            flush()
        previous_bottom = end
        line = line.replace("�", "–" if page_number == 5 else "•")
        if page_number == 1 and y < 185:
            flush()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(line)
            run.bold = y < 160
            run.font.size = Pt(14 if y < 160 else 12)
        elif re.match(r"^\d+(?:\.\d+)*\.?\s+[A-Z]|^LEMBAR PENGESAHAN$", line) and len(line) < 75:
            flush()
            doc.add_heading(line, level=1 if re.match(r"^\d+\.\s|^LEMBAR", line) else 2)
        elif line.startswith(("• ", "- ")):
            flush()
            paragraph.append(line[2:])
            bullet = True
        else:
            paragraph.append(line)
    flush()


def add_table(doc, page, table):
    rows = table.rows
    if not rows:
        return
    # PDF exports often split three visual columns into nine thin cell strips.
    # The strips are padding/borders, not actual data columns.
    three_columns = len(rows[0].cells) >= 9
    count = 3 if three_columns else len(rows[0].cells)
    output = doc.add_table(rows=0, cols=count)
    output.style = "Table Grid"
    output.alignment = WD_TABLE_ALIGNMENT.CENTER
    output.autofit = False
    if three_columns:
        for column, width in zip(output.columns, (0.48, 1.82, 3.85)):
            column.width = Inches(width)
    for index, row in enumerate(rows):
        cells = output.add_row().cells
        if three_columns:
            x0, y0, x1, y1 = row.bbox
            bounds = [(x0, 107.42), (107.42, 249.29), (249.29, x1)]
            values = [page.crop((max(0, left + 0.5), y0 + 0.5,
                                 min(page.width, right - 0.5), y1 - 0.5))
                      .extract_text(x_tolerance=2, y_tolerance=3) or ""
                      for left, right in bounds]
        else:
            values = []
            for bbox in row.cells:
                values.append((page.crop(bbox).extract_text(x_tolerance=2,
                                                             y_tolerance=3) or "") if bbox else "")
        for cell, value in zip(cells, values):
            cell.text = value.strip()
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(1)
                for run in p.runs:
                    run.font.size = Pt(9 if three_columns else 10)
            if index == 0 and three_columns:
                for run in cell.paragraphs[0].runs:
                    run.bold = True


def convert(source, target):
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.left_margin = section.right_margin = Inches(0.72)
    section.top_margin = section.bottom_margin = Inches(0.75)
    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(6)
    for name, size in (("Heading 1", 13), ("Heading 2", 11)):
        doc.styles[name].font.name = "Arial"
        doc.styles[name].font.size = Pt(size)
        doc.styles[name].font.bold = True

    with pdfplumber.open(source) as pdf:
        for number, page in enumerate(pdf.pages):
            if number:
                doc.add_page_break()
            cursor = 0
            for table in sorted(page.find_tables(), key=lambda item: item.bbox[1]):
                add_text(doc, page, cursor, table.bbox[1] - 1, number + 1)
                add_table(doc, page, table)
                cursor = table.bbox[3] + 1
            add_text(doc, page, cursor, page.height, number + 1)
    doc.save(target)


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
