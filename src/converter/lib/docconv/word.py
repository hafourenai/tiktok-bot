from ._ooxml import (OoxmlError, PackageReader, PackageWriter,
                     content_types_xml, descendants, find_all, local_name)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

DOCUMENT_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    f'<Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# -- writer ---------------------------------------------------------------
def write_docx(paragraphs, path) -> str:
    """Write paragraphs to a .docx.

    Each item is a str (one paragraph) or ``(text, style)`` where style is
    ``"pagebreak"`` for a page break or a heading level name.
    """
    body: list[str] = []
    for item in paragraphs:
        text, style = _normalise(item)
        if style == "pagebreak":
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
            continue
        if not str(text):
            body.append("<w:p/>")
            continue
        style_attr = ""
        if style and style != "normal":
            style_attr = f'<w:pStyle w:val="{_esc(style)}"/>'
        # Explicit xml:space="preserve" keeps leading/trailing spaces.
        body.append(
            f"<w:p><w:pPr>{style_attr}</w:pPr>"
            f'<w:r><w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>'
        )

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>'
        + "".join(body)
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
        "</w:body></w:document>"
    )

    writer = PackageWriter()
    writer.set("word/document.xml", document)
    writer.set("_rels/.rels", ROOT_RELS)
    writer.set("word/_rels/document.xml.rels", (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    ))
    return writer.write(path, content_types_xml([("/word/document.xml", DOCUMENT_CONTENT_TYPE)]))


def _normalise(item):
    if isinstance(item, tuple):
        return item[0], (item[1] if len(item) > 1 else "normal")
    return item, "normal"


# -- reader ---------------------------------------------------------------
class DocxReader:
    """Reads paragraph and table text from a .docx."""

    def __init__(self, path):
        self.package = PackageReader(path)
        self._document = None

    def close(self) -> None:
        self.package.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def document(self):
        if self._document is None:
            if not self.package.has("word/document.xml"):
                raise OoxmlError("Dokumen Word tidak memiliki word/document.xml.")
            self._document = self.package.xml("word/document.xml")
        return self._document

    def iter_blocks(self):
        """Yield ``('paragraph', text)`` and ``('table', rows)`` in order."""
        body = self._body()
        for child in body:
            name = local_name(child.tag)
            if name == "p":
                yield ("paragraph", paragraph_text(child))
            elif name == "tbl":
                yield ("table", table_rows(child))
            elif name == "sdt":  # structured document tag wrapper
                for nested in child.iter():
                    nested_name = local_name(nested.tag)
                    if nested is child:
                        continue
                    if nested_name == "p":
                        yield ("paragraph", paragraph_text(nested))
                    elif nested_name == "tbl":
                        yield ("table", table_rows(nested))

    def _body(self):
        for node in find_all(self.document, "body"):
            return node
        return self.document

    def paragraphs(self) -> list:
        return [text for kind, text in self.iter_blocks() if kind == "paragraph"]

    def tables(self) -> list:
        return [rows for kind, rows in self.iter_blocks() if kind == "table"]

    def text(self) -> str:
        """All text with tables flattened to ``a | b | c`` rows."""
        out = []
        for kind, value in self.iter_blocks():
            if kind == "paragraph":
                if value:
                    out.append(value)
            else:
                for row in value:
                    out.append(" | ".join(cell for cell in row))
        return "\n".join(out)


def paragraph_text(element) -> str:
    """Concatenate ``w:t`` runs in a paragraph, honouring tabs and breaks."""
    pieces = []
    for node in element.iter():
        name = local_name(node.tag)
        if name == "t":
            pieces.append(node.text or "")
        elif name == "tab":
            pieces.append("\t")
        elif name == "br":
            pieces.append("\n")
    return "".join(pieces)


def table_rows(element) -> list:
    rows = []
    for row in descendants(element, "tr"):
        cells = []
        for cell in descendants(row, "tc"):
            texts = [paragraph_text(p) for p in descendants(cell, "p")]
            cells.append("\n".join(t for t in texts if t))
        rows.append(cells)
    return rows


def read_docx(path):
    return DocxReader(path)


__all__ = ["write_docx", "read_docx", "DocxReader", "paragraph_text", "table_rows"]