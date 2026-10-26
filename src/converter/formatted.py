"""Optional editable, layout-aware PDF to DOCX backend.

Uses positioned PDF text and ruled tables when pdfplumber/python-docx are
installed. No source code from third-party converter projects is included.
"""

import re
from io import BytesIO


def convert_formatted_pdf_to_docx(source: str, target: str) -> str:
    import pdfplumber
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.shared import Inches, Pt

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.left_margin = section.right_margin = Inches(0.7)
    section.top_margin = section.bottom_margin = Inches(0.7)
    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(6)
    for name, size in (("Heading 1", 13), ("Heading 2", 11)):
        style = doc.styles[name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.bold = True
        style.paragraph_format.space_before = Pt(6)
        style.paragraph_format.space_after = Pt(6)

    def text_region(page, top, bottom, page_number):
        if bottom - top < 2:
            return
        lines = page.crop((0, top, page.width, bottom)).extract_text_lines(
            x_tolerance=2, y_tolerance=3)
        pending = []
        pending_fonts = []
        previous_bottom = None
        bullet = False

        def flush():
            nonlocal bullet
            if pending:
                text = " ".join(pending)
                p = doc.add_paragraph(text, style="List Bullet" if bullet else None)
                p.paragraph_format.line_spacing = 1.15
                # Apply font from first line in pending
                if pending_fonts:
                    font_name, font_size = pending_fonts[0]
                    is_bold = "Bold" in font_name
                    clean_font = font_name.replace("PS", "").replace("-Bold", "").replace("MT", "").strip()
                    clean_font = clean_font.split("+")[-1]  # Remove prefix like BCDFEE+
                    for run in p.runs:
                        run.font.name = clean_font if clean_font else "Times New Roman"
                        run.font.bold = is_bold
                        if font_size:
                            run.font.size = Pt(font_size)
                pending.clear()
                pending_fonts.clear()
            bullet = False

        for line in lines:
            text = line["text"].strip()
            if not text:
                flush()
                continue
            
            # Get font and size from first char in line
            font_from_line = None
            size_from_line = None
            if line.get("chars"):
                first_char = line["chars"][0]
                font_from_line = first_char.get("fontname", "")
                size_from_line = first_char.get("size", None)
            
            # Large gap = new paragraph
            if previous_bottom is not None and line["top"] - previous_bottom > 14:
                flush()
            
            previous_bottom = line["bottom"]
            text = text.replace("–", "–" if page_number == 5 else "•")
            
            heading = re.match(r"^\d+(?:\.\d+)*\.?\s+[A-Z]|^LEMBAR PENGESAHAN$", text)
            
            if page_number == 1 and line["top"] < 185:
                flush()
                paragraph = doc.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = paragraph.add_run(text)
                run.bold = line["top"] < 160
                run.font.size = Pt(14 if line["top"] < 160 else 12)
                run.font.name = "Times New Roman"
            elif heading and len(text) < 75:
                flush()
                h = doc.add_heading(text, level=1 if re.match(r"^\d+\.\s|^LEMBAR", text) else 2)
                h.alignment = WD_ALIGN_PARAGRAPH.LEFT
                h.paragraph_format.space_before = Pt(12)
                h.paragraph_format.space_after = Pt(6)
                # Apply font to heading
                for run in h.runs:
                    run.font.name = "Times New Roman"
                    if size_from_line:
                        run.font.size = Pt(size_from_line)
            elif text.startswith(("• ", "- ")):
                flush()
                pending.append(text[2:])
                pending_fonts.append((font_from_line or "", size_from_line))
                bullet = True
            else:
                pending.append(text)
                pending_fonts.append((font_from_line or "", size_from_line))
        flush()

    def add_table(page, table):
        # The PDF may split a visual header into tiny border-padding cells.
        # Infer actual columns from the first data row with unmerged cells.
        candidates = [row for row in table.rows if sum(c is not None for c in row.cells) >= 2]
        if not candidates:
            return
        sample = min(candidates, key=lambda row: sum(c is not None for c in row.cells))
        bounds = sorted({round(x, 1) for cell in sample.cells if cell
                         for x in (cell[0], cell[2])})
        if len(bounds) < 3 or len(bounds) > 12:
            return
        output = doc.add_table(rows=0, cols=len(bounds) - 1)
        output.style = "Table Grid"
        output.alignment = WD_TABLE_ALIGNMENT.CENTER
        output.autofit = False
        scale = 6.15 / (bounds[-1] - bounds[0])
        for column, (left, right) in zip(output.columns, zip(bounds, bounds[1:])):
            column.width = Inches((right - left) * scale)
        for index, row in enumerate(table.rows):
            cells = output.add_row().cells
            if len(bounds) > 3:
                cant_split = OxmlElement("w:cantSplit")
                output.rows[-1]._tr.get_or_add_trPr().append(cant_split)
            if index == 0 and len(bounds) > 3:
                repeat = OxmlElement("w:tblHeader")
                output.rows[-1]._tr.get_or_add_trPr().append(repeat)
            for col, (left, right) in enumerate(zip(bounds, bounds[1:])):
                top, bottom = row.bbox[1], row.bbox[3]
                if right - left < 2 or bottom - top < 2:
                    continue
                crop = page.crop((max(0, left + 0.5), top + 0.5,
                                   min(page.width, right - 0.5), bottom - 0.5))
                cells[col].text = (crop.extract_text(x_tolerance=2, y_tolerance=3) or "").strip()
                cells[col].width = Inches((right - left) * scale)
                cells[col].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                images = [image for image in page.images
                          if left <= (image["x0"] + image["x1"]) / 2 < right
                          and top <= (image["top"] + image["bottom"]) / 2 < bottom]
                for image in sorted(images, key=lambda item: item["top"]):
                    stream = image["stream"]
                    filters = stream.attrs.get("Filter")
                    filters = filters if isinstance(filters, list) else [filters]
                    if not any(str(value) == "/'DCTDecode'" for value in filters):
                        continue
                    above = page.crop((left, top, right, image["top"])).extract_text() or ""
                    below = page.crop((left, image["bottom"], right, bottom)).extract_text() or ""
                    cells[col].text = above.strip()
                    picture = cells[col].add_paragraph()
                    picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    width = min(image["width"] / 72, (right - left) * scale - 0.12)
                    picture.add_run().add_picture(
                        BytesIO(stream.get_data()), width=Inches(width),
                        height=Inches(width * image["height"] / image["width"]))
                    if below.strip():
                        cells[col].add_paragraph(below.strip())
                if index == 0 and len(bounds) > 3:
                    shading = OxmlElement("w:shd")
                    shading.set(qn("w:fill"), "EBEEF0")
                    cells[col]._tc.get_or_add_tcPr().append(shading)
                for paragraph in cells[col].paragraphs:
                    paragraph.paragraph_format.space_after = Pt(1)
                    for run in paragraph.runs:
                        run.font.size = Pt(9)
                        if index == 0 and len(bounds) > 3:
                            run.bold = True
                        elif col == 0 and len(bounds) == 3:
                            run.bold = True

    with pdfplumber.open(source) as pdf:
        if not pdf.pages:
            raise ValueError("PDF tidak memiliki halaman")
        if any(not page.extract_text().strip() for page in pdf.pages):
            raise ValueError("Halaman tanpa teks memerlukan OCR")
        for number, page in enumerate(pdf.pages):
            if number:
                doc.add_page_break()
            cursor = 0
            for table in sorted(page.find_tables(), key=lambda t: t.bbox[1]):
                text_region(page, cursor, table.bbox[1] - 1, number + 1)
                add_table(page, table)
                cursor = table.bbox[3] + 1
            text_region(page, cursor, page.height, number + 1)
    doc.save(target)
    return target
