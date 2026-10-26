import re

from ._ooxml import (OoxmlError, PackageReader, PackageWriter,
                     content_types_xml, descendants, find_all, local_name)

S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

WORKBOOK_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
SHEET_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
SHARED_STRINGS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml")

CELL_REF = re.compile(r"^([A-Za-z]+)(\d+)$")

# Excel's hard limits; exceeding them makes the file unopenable.
MAX_CELL = 32767
MAX_ROWS = 1048576
MAX_COLUMNS = 16384


class ExcelError(ValueError):
    """Raised when a workbook cannot be built or read."""


def column_to_index(letters: str) -> int:
    """``A`` -> 0, ``B`` -> 1, ``AA`` -> 26 (0-based)."""
    value = 0
    for char in letters.upper():
        value = value * 26 + (ord(char) - 64)
    return value - 1


def index_to_column(index: int) -> str:
    """0 -> ``A``, 26 -> ``AA``."""
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def split_ref(ref: str):
    """``B7`` -> ``(7, 1)`` as 1-based row, 0-based column."""
    match = CELL_REF.match(str(ref or "").strip())
    if not match:
        return None, None
    return int(match.group(2)), column_to_index(match.group(1))


def _esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


class Sheet:
    """An in-memory grid of string cells."""

    def __init__(self, title: str):
        self.title = title
        self.cells: dict[tuple, str] = {}  # (row 1-based, column 0-based) -> text

    def set(self, row: int, column: int, value) -> None:
        if value is None:
            return
        text = str(value)
        if text == "":
            return
        if row < 1 or row > MAX_ROWS:
            return
        if column < 0 or column >= MAX_COLUMNS:
            return
        if len(text) > MAX_CELL:
            text = text[:MAX_CELL]
        self.cells[(row, column)] = text

    def used_range(self):
        if not self.cells:
            return 0, 0
        max_row = max(key[0] for key in self.cells)
        max_column = max(key[1] for key in self.cells)
        return max_row, max_column

    def rows(self) -> list:
        """Dense row list padded to the used column count."""
        max_row, max_column = self.used_range()
        out = []
        for row in range(1, max_row + 1):
            out.append([self.cells.get((row, column), "")
                        for column in range(max_column + 1)])
        return out


# -- writer ---------------------------------------------------------------
def write_xlsx(sheets, path) -> str:
    """Write :class:`Sheet` objects to a .xlsx."""
    if not sheets:
        sheets = [Sheet("Sheet1")]

    shared: dict[str, int] = {}
    order: list[str] = []

    def intern(text: str) -> int:
        if text not in shared:
            shared[text] = len(order)
            order.append(text)
        return shared[text]

    sheet_xmls = []
    for sheet in sheets:
        sheet_xmls.append(_sheet_xml(sheet, intern))

    entries = []
    for index, sheet in enumerate(sheets, 1):
        rid = f"rId{index}"
        entries.append(f'<sheet name="{_esc(_safe_title(sheet.title, index))}" '
                       f'sheetId="{index}" r:id="{rid}"/>')

    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{S}" xmlns:r="{REL}">'
        f"<sheets>{''.join(entries)}</sheets></workbook>"
    )
    workbook_rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for index in range(1, len(sheets) + 1):
        workbook_rels.append(
            f'<Relationship Id="rId{index}" Type="{REL}/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
    count = len(sheets) + 1
    workbook_rels.append(
        f'<Relationship Id="rId{count}" Type="{REL}/sharedStrings" '
        f'Target="sharedStrings.xml"/>'
    )
    workbook_rels.append("</Relationships>")

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    writer = PackageWriter()
    writer.set("xl/workbook.xml", workbook)
    writer.set("xl/_rels/workbook.xml.rels", "".join(workbook_rels))
    writer.set("xl/sharedStrings.xml", _shared_strings_xml(order))
    writer.set("_rels/.rels", root_rels)
    overrides = [("/xl/workbook.xml", WORKBOOK_CONTENT_TYPE),
                  ("/xl/sharedStrings.xml", SHARED_STRINGS_CONTENT_TYPE)]
    for index, xml in enumerate(sheet_xmls, 1):
        writer.set(f"xl/worksheets/sheet{index}.xml", xml)
        overrides.append((f"/xl/worksheets/sheet{index}.xml", SHEET_CONTENT_TYPE))
    return writer.write(path, content_types_xml(overrides))


def _safe_title(title: str, index: int) -> str:
    """Sheet names cannot contain []:*?/\\ and are capped at 31 chars."""
    cleaned = "".join(c for c in str(title or "") if c not in "[]:*?/\\")
    cleaned = cleaned.strip("'") or f"Sheet{index}"
    return cleaned[:31]


def _shared_strings_xml(order) -> str:
    items = "".join(f"<si><t xml:space=\"preserve\">{_esc(text)}</t></si>"
                    for text in order)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="{S}" count="{len(order)}" uniqueCount="{len(order)}">'
        f"{items}</sst>"
    )


def _sheet_xml(sheet: Sheet, intern) -> str:
    by_row: dict[int, list] = {}
    for (row, column), text in sheet.cells.items():
        by_row.setdefault(row, []).append((column, text))
    parts = []
    for row in sorted(by_row):
        cells = []
        for column, text in sorted(by_row[row]):
            index = intern(text)
            ref = f"{index_to_column(column)}{row}"
            cells.append(
                f'<c r="{ref}" t="s"><v>{index}</v></c>'
            )
        parts.append(f'<row r="{row}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{S}"><sheetData>{"".join(parts)}</sheetData></worksheet>'
    )


# -- reader ---------------------------------------------------------------
class XlsxReader:
    """Reads cell values out of an .xlsx, preserving them as strings."""

    def __init__(self, path):
        self.package = PackageReader(path)
        self._shared: list | None = None
        self._sheets: list | None = None

    def close(self) -> None:
        self.package.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def shared_strings(self) -> list:
        if self._shared is None:
            self._shared = []
            if self.package.has("xl/sharedStrings.xml"):
                for item in find_all(self.package.xml("xl/sharedStrings.xml"), "si"):
                    self._shared.append(_si_text(item))
        return self._shared

    def sheets(self) -> list:
        """Return ``[(name, rows), ...]`` in workbook order."""
        if self._sheets is not None:
            return self._sheets
        if not self.package.has("xl/workbook.xml"):
            raise OoxmlError("Workbook tidak memiliki xl/workbook.xml.")
        workbook = self.package.xml("xl/workbook.xml")
        rels = self.package.relationships("xl/workbook.xml")
        # rId -> target, restricted to worksheet relationships.
        targets = {rid: target for rid, (kind, target) in rels.items()
                   if kind == "worksheet"}

        out = []
        for sheet in find_all(workbook, "sheet"):
            name = sheet.get("name") or f"Sheet{len(out) + 1}"
            rid = sheet.get(f"{{{REL}}}id") or sheet.get("id")
            target = targets.get(rid)
            if not target:
                continue
            part = self.package.resolve_target("xl/workbook.xml", target)
            if not self.package.has(part):
                continue
            out.append((name, self._read_sheet(self.package.xml(part))))
        self._sheets = out
        return out

    def _read_sheet(self, root) -> list:
        rows = []
        for row in find_all(root, "row"):
            values = {}
            for cell in descendants(row, "c"):
                ref = cell.get("r")
                row_index, column = split_ref(ref)
                if row_index is None:
                    continue
                values[column] = _cell_text(cell, self.shared_strings)
            if not values:
                rows.append([])
                continue
            width = max(values) + 1
            dense = [values.get(index, "") for index in range(width)]
            # Pad so the row index lines up with the sheet's row number.
            while len(rows) < row_index - 1:
                rows.append([])
            if len(rows) == row_index - 1:
                rows.append(dense)
            else:
                rows[row_index - 1] = dense
        return rows


def _si_text(element) -> str:
    """A shared string may be plain ``t`` or rich ``r`` runs."""
    return "".join(node.text or "" for node in element.iter()
                   if local_name(node.tag) == "t")


def _cell_text(cell, shared) -> str:
    kind = cell.get("t")
    value_node = None
    for child in cell:
        if local_name(child.tag) == "v":
            value_node = child
            break
    if kind == "s":
        if value_node is None or value_node.text is None:
            return ""
        try:
            index = int(value_node.text)
        except ValueError:
            return ""
        return shared[index] if 0 <= index < len(shared) else ""
    if kind in ("inlineStr", "str"):
        return _si_text(cell)
    if value_node is None:
        return ""
    text = value_node.text or ""
    if kind == "b":
        return "TRUE" if text == "1" else "FALSE"
    return text


def read_xlsx(path):
    return XlsxReader(path)


__all__ = ["write_xlsx", "read_xlsx", "XlsxReader", "Sheet", "ExcelError",
           "column_to_index", "index_to_column", "split_ref"]