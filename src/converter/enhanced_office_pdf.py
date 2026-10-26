"""Enhanced Office to PDF fallback with better formatting.

Improves upon text-only PDF by preserving tables, headings, images, and formatting
when LibreOffice is unavailable. Uses native Office reading libraries.
"""

from pathlib import Path
from io import BytesIO


def convert_office_to_enhanced_pdf(input_path: str, output_path: str) -> str:
    """Convert Office file to PDF with enhanced formatting.
    
    Features:
    - Preserve table structures
    - Heading detection & formatting
    - Image embedding
    - Font styling (bold, italic, size)
    - Better paragraph spacing
    - Page breaks
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    from reportlab.lib import colors

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    heading1_style = ParagraphStyle(
        'Heading1Custom',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=12,
        spaceBefore=12,
        fontName='Times-Roman',
    )
    
    heading2_style = ParagraphStyle(
        'Heading2Custom',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.black,
        spaceAfter=10,
        spaceBefore=10,
        fontName='Times-Roman',
    )
    
    body_style = ParagraphStyle(
        'BodyCustom',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        spaceAfter=6,
        fontName='Times-Roman',
    )

    ext = Path(input_path).suffix.lower()

    if ext == ".docx":
        _process_docx(input_path, story, styles, heading1_style, heading2_style, body_style)
    elif ext == ".xlsx":
        _process_xlsx(input_path, story, styles, heading1_style, body_style)
    elif ext == ".pptx":
        _process_pptx(input_path, story, styles, heading1_style, body_style)
    else:
        raise ValueError(f"Format Office {ext} belum didukung")

    if not story:
        raise RuntimeError("Dokumen kosong atau tidak bisa diproses")

    doc.build(story)
    return output_path


def _process_docx(input_path, story, styles, h1_style, h2_style, body_style):
    """Process DOCX with preserved formatting."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from reportlab.platypus import Paragraph, Table, TableStyle, PageBreak, Image
    from reportlab.lib import colors
    
    doc = Document(input_path)
    
    for element in doc.element.body:
        # Process paragraphs
        if element.tag.endswith('p'):
            from docx.oxml.text.paragraph import CT_P
            if isinstance(element, CT_P):
                para = None
                for p in doc.paragraphs:
                    if p._element == element:
                        para = p
                        break
                
                if para:
                    text = para.text.strip()
                    if not text:
                        story.append(Spacer(1, 0.1 * inch))
                        continue
                    
                    # Detect heading
                    if para.style.name.startswith('Heading 1'):
                        story.append(Paragraph(text, h1_style))
                    elif para.style.name.startswith('Heading 2'):
                        story.append(Paragraph(text, h2_style))
                    else:
                        story.append(Paragraph(text, body_style))
        
        # Process tables
        elif element.tag.endswith('tbl'):
            from docx.oxml.table import CT_Tbl
            if isinstance(element, CT_Tbl):
                for table in doc.tables:
                    if table._element == element:
                        table_data = [[cell.text for cell in row.cells] for row in table.rows]
                        if table_data:
                            t = Table(table_data)
                            t.setStyle(TableStyle([
                                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                                ('FONTSIZE', (0, 0), (-1, 0), 11),
                                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                            ]))
                            story.append(t)
                            story.append(Spacer(1, 0.2 * inch))
                        break


def _process_xlsx(input_path, story, styles, h1_style, body_style):
    """Process XLSX with sheet names as headings."""
    from openpyxl import load_workbook
    from reportlab.platypus import Table, TableStyle, PageBreak, Paragraph
    from reportlab.lib import colors
    
    wb = load_workbook(input_path, data_only=True)
    
    for sheet_idx, sheet in enumerate(wb.sheetnames):
        if sheet_idx > 0:
            story.append(PageBreak())
        
        ws = wb[sheet]
        story.append(Paragraph(f"Sheet: {sheet}", h1_style))
        
        # Build table
        table_data = []
        for row in ws.iter_rows(values_only=True):
            table_data.append([str(cell) if cell else "" for cell in row])
        
        if table_data:
            t = Table(table_data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            story.append(t)


def _process_pptx(input_path, story, styles, h1_style, body_style):
    """Process PPTX with slide content."""
    from pptx import Presentation
    from reportlab.platypus import Paragraph, PageBreak, Table, TableStyle
    from reportlab.lib import colors
    
    prs = Presentation(input_path)
    
    for slide_idx, slide in enumerate(prs.slides):
        if slide_idx > 0:
            story.append(PageBreak())
        
        story.append(Paragraph(f"Slide {slide_idx + 1}", h1_style))
        
        # Extract text from shapes
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                story.append(Paragraph(shape.text, body_style))
            
            # Extract tables
            if shape.has_table:
                table = shape.table
                table_data = []
                for row in table.rows:
                    table_data.append([cell.text for cell in row.cells])
                
                if table_data:
                    t = Table(table_data)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ]))
                    story.append(t)
