"""PDF writer for text-only fallback conversions.

Minimal, deterministic PDF producer using base-14 Courier font.
Suitable for fallback when rich formatting is not available.
"""

import zlib

PAGE_WIDTH = 595.276  # A4 in points
PAGE_HEIGHT = 841.890
MARGIN = 56.7  # 2 cm

FONT_NAME = "Courier"
FONT_SIZE = 11.0
# Courier advance width is 600/1000 em for every glyph.
GLYPH_WIDTH_RATIO = 0.6
LINE_HEIGHT_RATIO = 1.35


class Page:
    """One output page accumulating text-drawing operators."""

    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
        self.parts: list[str] = []
        self.images: list[str] = []

    def draw_text(self, x: float, y: float, text: str, size: float = FONT_SIZE) -> None:
        escaped = _escape_pdf_text(text)
        if not escaped:
            return
        self.parts.append(
            f"BT /F1 {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({escaped}) Tj ET"
        )

    def draw_image(self, image, x: float, y: float,
                   width: float, height: float) -> None:
        """Place a :class:`PlacedImage` filling the given user-space box."""
        name = f"Im{len(self.images)}"
        self.images.append(image)
        self.parts.append(
            f"q {width:.2f} 0 0 {height:.2f} {x:.2f} {y:.2f} cm /{name} Do Q"
        )

    def content(self) -> bytes:
        return ("\n".join(self.parts)).encode("latin-1", "replace")


class PdfWriter:
    """Accumulates pages and serialises a classic (non-streamed) PDF."""

    def __init__(self, compress: bool = True):
        self.pages: list[Page] = []
        self.compress = compress

    def add_page(self, width: float = PAGE_WIDTH, height: float = PAGE_HEIGHT) -> Page:
        page = Page(width, height)
        self.pages.append(page)
        return page

    # -- serialisation -----------------------------------------------------
    def write(self, path) -> str:
        objects: list[bytes] = []

        def add(payload: bytes) -> int:
            objects.append(payload)
            return len(objects)  # object numbers are 1-based

        # 1: catalog, 2: pages -- reserved up front so pages can reference them.
        catalog_num = add(b"<< /Type /Catalog /Pages 2 0 R >>")
        pages_num = add(b"<< /Type /Pages /Kids [] /Count 0 >>")

        font_num = add(
            f"<< /Type /Font /Subtype /Type1 /BaseFont /{FONT_NAME} "
            f"/Encoding /WinAnsiEncoding >>".encode("latin-1")
        )

        kids: list[str] = []
        for page in self.pages:
            content = page.content()
            if self.compress and content:
                stream = zlib.compress(content, 6)
                content_obj = add(
                    b"<< /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream"
                    % (len(stream), stream)
                )
            else:
                content_obj = add(
                    b"<< /Length %d >>\nstream\n%s\nendstream"
                    % (len(content), content)
                )

            xobjects = ""
            for index, image in enumerate(page.images):
                xobjects += f"/Im{index} {add(_image_object(image))} 0 R "
            resources = f"<< /Font << /F1 {font_num} 0 R >>"
            if page.images:
                resources += f" /XObject << {xobjects}>>"
            resources += " >>"
            resources_num = add(resources.encode("latin-1"))

            page_num = add(
                f"<< /Type /Page /Parent {pages_num} 0 R "
                f"/MediaBox [0 0 {page.width:.2f} {page.height:.2f}] "
                f"/Resources {resources_num} 0 R "
                f"/Contents {content_obj} 0 R >>".encode("latin-1")
            )
            kids.append(f"{page_num} 0 R")

        objects[pages_num - 1] = (
            f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
        ).encode("latin-1")

        return _serialise(path, objects, catalog_num)


def _image_object(image: "PlacedImage") -> bytes:
    """Serialise one placed image as an image XObject stream."""
    header = (
        f"<< /Type /XObject /Subtype /Image "
        f"/Width {image.pixel_width} /Height {image.pixel_height} "
        f"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
        f"/Filter /{image.filter_name} /Length {len(image.blob)} >>\nstream\n"
    ).encode("latin-1")
    return header + image.blob + b"\nendstream"


class PlacedImage:
    """An image stream plus the pixel geometry needed in its XObject dict."""

    __slots__ = ("blob", "pixel_width", "pixel_height", "filter_name")

    def __init__(self, blob: bytes, pixel_width: int, pixel_height: int,
                 filter_name: str):
        self.blob = blob
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height
        self.filter_name = filter_name


def _serialise(path, objects: list, catalog_num: int) -> str:
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, payload in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("latin-1")
        out += payload
        out += b"\nendobj\n"
    xref_pos = len(out)
    count = len(objects) + 1
    out += f"xref\n0 {count}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {count} /Root {catalog_num} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("latin-1")
    with open(path, "wb") as handle:
        handle.write(bytes(out))
    return str(path)


def _escape_pdf_text(text: str) -> str:
    out = []
    for char in text:
        code = ord(char)
        if char in "()\\":
            out.append("\\" + char)
        elif code < 32 or code > 126:
            # WinAnsi covers Latin-1 plus a few specials; anything else becomes
            # a replacement so the output never becomes invalid.
            out.append("?")
        else:
            out.append(char)
    return "".join(out)


def text_width(text: str, size: float = FONT_SIZE) -> float:
    """Advance width of ``text`` in Courier, which is fixed-pitch."""
    return len(text) * GLYPH_WIDTH_RATIO * size


def wrap(text: str, size: float, max_width: float) -> list:
    """Greedy word wrap using the fixed-pitch Courier advance.

    Words longer than the line are hard-split rather than overflowing, which
    matters because the Office fallback feeds it arbitrarily long cells.
    """
    if max_width <= 0:
        return [text]
    limit = max(1, int(max_width / (GLYPH_WIDTH_RATIO * size)))
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            while len(word) > limit:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:limit])
                word = word[limit:]
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= limit:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def write_text_pdf(paragraphs, path, page_width: float = PAGE_WIDTH,
                   page_height: float = PAGE_HEIGHT, size: float = FONT_SIZE) -> str:
    """Write a list of text paragraphs to a paginated PDF.

    ``paragraphs`` items may be ``str`` or ``(text, is_page_break)`` tuples;
    a page break starts a new page before that text.
    """
    writer = PdfWriter()
    page = writer.add_page(page_width, page_height)
    y = page_height - MARGIN
    bottom = MARGIN
    step = size * LINE_HEIGHT_RATIO
    usable = page_width - 2 * MARGIN
    pending_break = False

    def new_page():
        nonlocal page, y
        page = writer.add_page(page_width, page_height)
        y = page_height - MARGIN

    for item in paragraphs:
        if isinstance(item, tuple):
            text, pending_break = item
        else:
            text, pending_break = item, False
        if pending_break and (page.parts or page.images):
            new_page()
        if not str(text).strip():
            continue
        for line in wrap(str(text), size, usable):
            if y < bottom:
                new_page()
            page.draw_text(MARGIN, y, line, size)
            y -= step
        y -= step * 0.35  # paragraph spacing
        if y < bottom:
            new_page()
    return writer.write(path)


__all__ = ["PdfWriter", "Page", "write_text_pdf", "wrap", "text_width",
           "PAGE_WIDTH", "PAGE_HEIGHT", "MARGIN"]