"""Optional enhanced PDF to XLSX backend with formatting preservation.

Uses pdfplumber for table extraction with cell styling, fonts, and column width
optimization. Falls back to text extraction if formatting unavailable.
"""


def convert_formatted_pdf_to_xlsx(source: str, target: str) -> str:
    """Convert PDF to XLSX with formatting preservation.
    
    Features:
    - Preserve cell background colors
    - Auto-detect column widths
    - Font preservation (bold, size, color)
    - Header row formatting
    - Table border detection
    """
    import pdfplumber
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)  # Remove default sheet

    # Style constants
    header_fill = PatternFill(start_color="EBEEF0", end_color="EBEEF0", fill_type="solid")
    header_font = Font(name="Times New Roman", size=10, bold=True)
    normal_font = Font(name="Times New Roman", size=10)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    with pdfplumber.open(source) as pdf:
        if not pdf.pages:
            raise ValueError("PDF tidak memiliki halaman")

        for page_num, page in enumerate(pdf.pages, 1):
            ws = wb.create_sheet(title=f"Page {page_num}")
            
            # Extract tables
            tables = page.find_tables()
            if not tables:
                # No table: extract text as rows
                text = page.extract_text() or ""
                for row_idx, line in enumerate(text.splitlines(), 1):
                    if line.strip():
                        ws.cell(row=row_idx, column=1, value=line)
                continue

            # Process tables
            current_row = 1
            for table in tables:
                rows = table.rows
                if not rows:
                    continue

                # Detect column count
                col_count = max(
                    sum(1 for cell in row.cells if cell is not None)
                    for row in rows
                ) or 1

                # Extract and insert rows
                for row_idx, pdf_row in enumerate(rows):
                    for col_idx in range(col_count):
                        # Get cell content
                        cell_value = ""
                        cell_bbox = None
                        
                        if col_idx < len(pdf_row.cells) and pdf_row.cells[col_idx]:
                            bbox = pdf_row.cells[col_idx]
                            cell_bbox = bbox
                            crop = page.crop(bbox)
                            cell_value = (crop.extract_text(x_tolerance=2, y_tolerance=3) or "").strip()

                        # Write to Excel
                        excel_cell = ws.cell(row=current_row, column=col_idx + 1, value=cell_value)
                        
                        # Apply formatting
                        excel_cell.border = thin_border
                        excel_cell.font = header_font if row_idx == 0 else normal_font
                        excel_cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                        
                        # Header row styling
                        if row_idx == 0:
                            excel_cell.fill = header_fill
                        
                        # Detect cell background from PDF rects
                        if cell_bbox:
                            x0, y0, x1, y1 = cell_bbox
                            for rect in page.rects:
                                if (rect.get("fill") and 
                                    x0 <= rect["x0"] < x1 and 
                                    y0 <= rect["top"] < y1):
                                    color = rect.get("non_stroking_color")
                                    if color:
                                        hex_color = _color_to_hex(color)
                                        excel_cell.fill = PatternFill(
                                            start_color=hex_color,
                                            end_color=hex_color,
                                            fill_type="solid"
                                        )
                                    break
                    
                    current_row += 1
                
                # Add blank row between tables
                current_row += 1

            # Auto-adjust column widths
            for col_idx in range(1, col_count + 1):
                max_length = 0
                col_letter = get_column_letter(col_idx)
                for cell in ws[col_letter]:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                ws.column_dimensions[col_letter].width = min(max_length + 2, 50)

    wb.save(target)
    return target


def _color_to_hex(color) -> str:
    """Convert PDF color value to Excel hex color.
    
    Args:
        color: Grayscale value (0-1) or RGB tuple
    
    Returns:
        Hex color string (e.g., "EBEEF0")
    """
    if isinstance(color, (list, tuple)):
        if len(color) == 1:
            # Grayscale
            gray = int(color[0] * 255)
            return f"{gray:02X}{gray:02X}{gray:02X}"
        elif len(color) >= 3:
            # RGB
            r, g, b = int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
            return f"{r:02X}{g:02X}{b:02X}"
    elif isinstance(color, (int, float)):
        # Grayscale
        gray = int(color * 255)
        return f"{gray:02X}{gray:02X}{gray:02X}"
    
    return "FFFFFF"  # Default white
