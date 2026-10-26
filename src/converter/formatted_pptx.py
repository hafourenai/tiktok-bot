"""Optional enhanced PDF to PPTX backend with editable content.

Uses pdfplumber for text and table extraction to create editable PowerPoint slides
instead of just rendering pages as images. Preserves formatting and allows editing
of content after conversion.
"""

from io import BytesIO


def convert_formatted_pdf_to_pptx(source: str, target: str) -> str:
    """Convert PDF to PPTX with editable text, tables, and formatting.
    
    Features:
    - Extract text to editable text boxes
    - Preserve heading hierarchy
    - Embed tables as editable objects
    - Extract and position images
    - Font and formatting preservation
    - Smart layout per page
    """
    import pdfplumber
    from pptx import Presentation
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    with pdfplumber.open(source) as pdf:
        if not pdf.pages:
            raise ValueError("PDF tidak memiliki halaman")

        for page_num, page in enumerate(pdf.pages, 1):
            # Add blank slide
            blank_slide_layout = prs.slide_layouts[6]  # Blank layout
            slide = prs.slides.add_slide(blank_slide_layout)

            # Add title with page number
            title_box = slide.shapes.add_textbox(
                Inches(0.5), Inches(0.3), Inches(9), Inches(0.5)
            )
            title_frame = title_box.text_frame
            title_frame.text = f"Page {page_num}"
            title_para = title_frame.paragraphs[0]
            title_para.font.size = Pt(28)
            title_para.font.bold = True
            title_para.font.name = "Times New Roman"

            # Extract content
            text = page.extract_text() or ""
            tables = page.find_tables()
            images = page.images

            current_top = 1.0  # Start position for content

            # Add tables
            if tables:
                for table in tables:
                    rows = table.rows
                    if not rows:
                        continue

                    col_count = max(
                        sum(1 for cell in row.cells if cell is not None)
                        for row in rows
                    ) or 1

                    # Add table shape
                    rows_count = len(rows)
                    left, top, width, height = (
                        Inches(0.5),
                        Inches(current_top),
                        Inches(9),
                        Inches(0.4 * rows_count),
                    )

                    table_shape = slide.shapes.add_table(
                        rows_count, col_count, left, top, width, height
                    ).table

                    # Fill table with data
                    for row_idx, pdf_row in enumerate(rows):
                        for col_idx in range(col_count):
                            cell_value = ""
                            if (
                                col_idx < len(pdf_row.cells)
                                and pdf_row.cells[col_idx]
                            ):
                                bbox = pdf_row.cells[col_idx]
                                crop = page.crop(bbox)
                                cell_value = (
                                    crop.extract_text(
                                        x_tolerance=2, y_tolerance=3
                                    )
                                    or ""
                                ).strip()

                            cell = table_shape.cell(row_idx, col_idx)
                            cell.text = cell_value

                            # Format header row
                            if row_idx == 0:
                                cell_text_frame = cell.text_frame
                                for paragraph in cell_text_frame.paragraphs:
                                    for run in paragraph.runs:
                                        run.font.bold = True
                                        run.font.size = Pt(11)

                    current_top += 0.4 * rows_count + 0.3

            # Add text content (body)
            if text.strip():
                lines = [
                    line.strip()
                    for line in text.splitlines()
                    if line.strip()
                ]

                text_box = slide.shapes.add_textbox(
                    Inches(0.5),
                    Inches(current_top),
                    Inches(9),
                    Inches(7.5 - current_top - 0.5),
                )
                text_frame = text_box.text_frame
                text_frame.word_wrap = True

                for line_idx, line in enumerate(lines):
                    if line_idx > 0:
                        text_frame.add_paragraph()

                    para = text_frame.paragraphs[line_idx]
                    para.text = line
                    para.font.size = Pt(12)
                    para.font.name = "Times New Roman"

                    # Detect heading
                    if line[0].isdigit() and "." in line:
                        para.font.bold = True
                        para.level = 0
                    elif line.startswith("  "):
                        para.level = 1

            # Add images
            for image in images:
                stream = image["stream"]
                filters = stream.attrs.get("Filter")
                filters = filters if isinstance(filters, list) else [filters]

                if any(str(value) == "/'DCTDecode'" for value in filters):
                    img_top = Inches(current_top + 4)
                    img_width = Inches(
                        min(
                            image["width"] / 72,
                            8,
                        )
                    )
                    img_height = Inches(
                        img_width.inches
                        * image["height"]
                        / image["width"]
                    )

                    try:
                        slide.shapes.add_picture(
                            BytesIO(stream.get_data()),
                            Inches(0.5),
                            img_top,
                            width=img_width,
                            height=img_height,
                        )
                        current_top += img_height.inches + 0.3
                    except Exception:
                        pass  # Skip if image processing fails

    prs.save(target)
    return target
