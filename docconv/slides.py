"""PPTX reader and writer.

Handles PresentationML format with minimal but valid relationship chains.
Reads text and image geometry from slides.
"""

from ._ooxml import (OoxmlError, PackageReader, PackageWriter,
                     content_types_xml, find_all, local_name, rels_xml)

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

PRESENTATION_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml")
SLIDE_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
SLIDE_LAYOUT_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml")
SLIDE_MASTER_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml")
THEME_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.theme+xml")

# 16:9 at 10 inches wide, matching PowerPoint's default widescreen size.
DEFAULT_WIDTH = 9144000
DEFAULT_HEIGHT = 5143500
EMU_PER_INCH = 914400


def _esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


class Slide:
    """One slide: text boxes and pictures in the order they were added."""

    def __init__(self):
        self.texts: list[str] = []
        self.pictures: list = []  # (left, top, width, height) EMU

    def add_text(self, text: str) -> None:
        if text and str(text).strip():
            self.texts.append(str(text))

    def add_picture(self, left: int, top: int, width: int, height: int) -> None:
        self.pictures.append((int(left), int(top), int(width), int(height)))


# -- writer ---------------------------------------------------------------
def write_pptx(slides, path, slide_width: int = DEFAULT_WIDTH,
               slide_height: int = DEFAULT_HEIGHT, pictures=None) -> str:
    """Write slides to a .pptx.

    ``slides`` is an iterable of :class:`Slide` or plain strings. ``pictures``
    is an optional parallel list of lists of image paths; each becomes a
    picture shape covering the given position.
    """
    writer = PackageWriter()
    slides = list(slides) or [Slide()]
    pictures = list(pictures) if pictures is not None else [[] for _ in slides]

    # Fixed relationship numbering keeps the parts easy to follow.
    # presentation.xml: rId1..N slides, then rId{N+1} master.
    count = len(slides)
    pres_rels = [
        ("rId1", "slideMaster", "slideMasters/slideMaster1.xml"),
    ]
    pres_entries = []
    for index in range(count):
        rid = f"rId{index + 1}"
        pres_rels.append((rid, "slide", f"slides/slide{index + 1}.xml"))
        pres_entries.append(
            f'<p:sldId id="{256 + index}" r:id="{rid}"/>'
        )
    pres_rels.append((f"rId{count + 1}", "theme", "theme/theme1.xml"))

    presentation = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:presentation xmlns:a="{A}" xmlns:r="{REL}" xmlns:p="{P}">'
        f'<p:sldSz cx="{int(slide_width)}" cy="{int(slide_height)}"/>'
        f'<p:sldIdLst>{"".join(pres_entries)}</p:sldIdLst>'
        "</p:presentation>"
    )

    writer.set("ppt/presentation.xml", presentation)
    writer.set("ppt/_rels/presentation.xml.rels", rels_xml(pres_rels))
    writer.set("ppt/slideMasters/slideMaster1.xml", _slide_master_xml())
    writer.set("ppt/slideMasters/_rels/slideMaster1.xml.rels", rels_xml([
        ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
        ("rId2", "theme", "../theme/theme1.xml"),
    ]))
    writer.set("ppt/slideLayouts/slideLayout1.xml", _slide_layout_xml())
    writer.set("ppt/slideLayouts/_rels/slideLayout1.xml.rels", rels_xml([
        ("rId1", "slideMaster", "../slideMasters/slideMaster1.xml"),
    ]))
    writer.set("ppt/theme/theme1.xml", _theme_xml())

    for index, slide in enumerate(slides, 1):
        slide_xml, slide_rels, extra_parts = _slide_xml(slide, pictures[index - 1])
        writer.set(f"ppt/slides/slide{index}.xml", slide_xml)
        rels = [("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml")]
        for image_index, (target, _name, _ext) in enumerate(extra_parts, 2):
            # Targets are relative to ppt/slides/, so media lives one level up.
            rels.append((f"rId{image_index}", "image", f"../{target}"))
        writer.set(f"ppt/slides/_rels/slide{index}.xml.rels", rels_xml(rels))
        for target, name, blob in extra_parts:
            writer.set(f"ppt/{target}", blob)

    writer.set("_rels/.rels", (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="ppt/presentation.xml"/>'
        "</Relationships>"
    ))

    overrides = [("/ppt/presentation.xml", PRESENTATION_CONTENT_TYPE),
                 ("/ppt/slideMasters/slideMaster1.xml", SLIDE_MASTER_CONTENT_TYPE),
                 ("/ppt/slideLayouts/slideLayout1.xml", SLIDE_LAYOUT_CONTENT_TYPE),
                 ("/ppt/theme/theme1.xml", THEME_CONTENT_TYPE)]
    for index in range(1, count + 1):
        overrides.append((f"/ppt/slides/slide{index}.xml", SLIDE_CONTENT_TYPE))
    content_types = content_types_xml(overrides)
    if any(name.endswith(".png") for name in writer.parts):
        content_types = content_types.replace(
            "</Types>",
            '<Default Extension="png" ContentType="image/png"/></Types>')
    return writer.write(path, content_types)


def _theme_xml() -> str:
    """A minimal but schema-valid theme with one colour and font scheme."""
    font_scheme = (
        '<a:fontScheme name="Office">'
        '<a:majorFont><a:latin typeface="Calibri Light"/><a:ea typeface=""/>'
        '<a:cs typeface=""/></a:majorFont>'
        '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/>'
        '<a:cs typeface=""/></a:minorFont>'
        "</a:fontScheme>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<a:theme xmlns:a="{A}" name="Office Theme">'
        "<a:themeElements>"
        f"<a:clrScheme name=\"Office\">{_colour_scheme()}</a:clrScheme>"
        f"{font_scheme}"
        '<a:fmtScheme name="Office">'
        "<a:fillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:fillStyleLst>"
        "<a:lnStyleLst>"
        "<a:ln><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln>"
        "<a:ln><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln>"
        "<a:ln><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln>"
        "</a:lnStyleLst>"
        "<a:effectStyleLst>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "</a:effectStyleLst>"
        "<a:bgFillStyleLst>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
        "</a:bgFillStyleLst>"
        "</a:fmtScheme>"
        "</a:themeElements>"
        "</a:theme>"
    )


def _colour_scheme() -> str:
    pairs = [("dk1", "sysClr", 'val="windowText" lastClr="000000"'),
             ("lt1", "sysClr", 'val="window" lastClr="FFFFFF"'),
             ("dk2", "srgbClr", 'val="44546A"'),
             ("lt2", "srgbClr", 'val="E7E6E6"'),
             ("accent1", "srgbClr", 'val="4472C4"'),
             ("accent2", "srgbClr", 'val="ED7D31"'),
             ("accent3", "srgbClr", 'val="A5A5A5"'),
             ("accent4", "srgbClr", 'val="FFC000"'),
             ("accent5", "srgbClr", 'val="5B9BD5"'),
             ("accent6", "srgbClr", 'val="70AD47"'),
             ("hlink", "srgbClr", 'val="0563C1"'),
             ("folHlink", "srgbClr", 'val="954F72"')]
    return "".join(f'<a:{name}><a:{kind} {attrs}/></a:{name}>'
                   for name, kind, attrs in pairs)


def _slide_master_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sldMaster xmlns:a="{A}" xmlns:r="{REL}" xmlns:p="{P}">'
        "<p:cSld><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        "<p:grpSpPr/>"
        "</p:spTree></p:cSld>"
        "<p:sldLayoutIdLst><p:sldLayoutId id=\"2147483649\" "
        "r:id=\"rId1\"/></p:sldLayoutIdLst>"
        "</p:sldMaster>"
    )


def _slide_layout_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sldLayout xmlns:a="{A}" xmlns:r="{REL}" xmlns:p="{P}" '
        'type="blank" preserve="1">'
        "<p:cSld name=\"Blank\"><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        "<p:grpSpPr/>"
        "</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sldLayout>"
    )


def _text_body(text: str) -> str:
    """A text body with one paragraph per source line."""
    paragraphs = []
    for line in str(text).split("\n"):
        paragraphs.append(
            f'<a:p><a:r><a:rPr lang="id-ID" dirty="0"/>'
            f'<a:t>{_esc(line)}</a:t></a:r></a:p>'
        )
    return (
        "<p:txBody><a:bodyPr wrap=\"square\"/><a:lstStyle/>"
        + "".join(paragraphs) + "</p:txBody>"
    )


def _slide_xml(slide: Slide, pictures):
    """Return ``(xml, rels, extra_parts)`` for one slide."""
    shapes = []
    extra_parts = []
    shape_id = 2

    for text in slide.texts:
        shapes.append(
            '<p:sp><p:nvSpPr>'
            f'<p:cNvPr id="{shape_id}" name="TextBox {shape_id}"/>'
            '<p:cNvSpPr txBox="1"/><p:nvPr/>'
            "</p:nvSpPr>"
            '<p:spPr><a:xfrm><a:off x="685800" y="457200"/>'
            f'<a:ext cx="{DEFAULT_WIDTH - 1371600}" cy="1828800"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            "</p:spPr>"
            + _text_body(text) +
            "</p:sp>"
        )
        shape_id += 1

    for index, picture in enumerate(pictures):
        image_bytes, ext = _load_image(picture)
        if image_bytes is None:
            continue
        name = f"image{index + 1}.{ext}"
        extra_parts.append((f"media/{name}", name, image_bytes))
        rid = f"rId{index + 2}"
        left, top, width, height = _picture_geometry(slide, picture, index)
        shapes.append(
            "<p:pic><p:nvPicPr>"
            f'<p:cNvPr id="{shape_id}" name="Picture {index + 1}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>'
            "<p:nvPr/></p:nvPicPr>"
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            "<p:spPr><a:xfrm>"
            f'<a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/>'
            "</a:xfrm>"
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            "</p:spPr></p:pic>"
        )
        shape_id += 1

    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sld xmlns:a="{A}" xmlns:r="{REL}" xmlns:p="{P}">'
        "<p:cSld><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        "<p:grpSpPr/>"
        + "".join(shapes) +
        "</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sld>"
    )
    return xml, None, extra_parts


def _picture_geometry(slide: Slide, picture, index: int):
    if index < len(slide.pictures):
        left, top, width, height = slide.pictures[index]
        return int(left), int(top), int(width), int(height)
    return 0, 0, DEFAULT_WIDTH, DEFAULT_HEIGHT


def _load_image(path):
    """Read an image file as bytes plus its extension, or (None, None)."""
    try:
        with open(path, "rb") as handle:
            blob = handle.read()
    except OSError:
        return None, None
    suffix = str(path).rsplit(".", 1)[-1].lower() if "." in str(path) else "png"
    if suffix not in ("png", "jpg", "jpeg"):
        suffix = "png"
    return blob, suffix


# -- reader ---------------------------------------------------------------
class PptxReader:
    """Reads slide text and picture geometry from a .pptx."""

    def __init__(self, path):
        self.package = PackageReader(path)

    def close(self) -> None:
        self.package.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def slides(self) -> list:
        """Return a list of :class:`Slide` objects in presentation order."""
        if not self.package.has("ppt/presentation.xml"):
            raise OoxmlError("Presentasi tidak memiliki ppt/presentation.xml.")
        presentation = self.package.xml("ppt/presentation.xml")
        rels = self.package.relationships("ppt/presentation.xml")
        targets = {rid: target for rid, (kind, target) in rels.items()
                   if kind == "slide"}

        out = []
        for entry in find_all(presentation, "sldId"):
            rid = entry.get(f"{{{REL}}}id")
            target = targets.get(rid)
            if not target:
                continue
            part = self.package.resolve_target("ppt/presentation.xml", target)
            if not self.package.has(part):
                continue
            out.append(self._read_slide(part))
        return out

    def _read_slide(self, part: str) -> Slide:
        root = self.package.xml(part)
        slide = Slide()
        for shape in root.iter():
            name = local_name(shape.tag)
            if name == "t":
                slide.texts.append(shape.text or "")
            elif name == "pic":
                slide.pictures.append(self._picture_geometry(shape))
        return slide

    def _picture_geometry(self, picture):
        offset = extent = None
        for node in picture.iter():
            name = local_name(node.tag)
            if name == "off" and offset is None:
                offset = (int(node.get("x", 0)), int(node.get("y", 0)))
            elif name == "ext" and extent is None:
                extent = (int(node.get("cx", 0)), int(node.get("cy", 0)))
        if offset and extent:
            return (offset[0], offset[1], extent[0], extent[1])
        return (0, 0, 0, 0)

    def text(self) -> str:
        """All slide text, slides separated by blank lines."""
        parts = []
        for slide in self.slides():
            parts.append("\n".join(slide.texts))
        return "\n\n".join(parts)


def read_pptx(path):
    return PptxReader(path)


__all__ = ["write_pptx", "read_pptx", "PptxReader", "Slide", "DEFAULT_WIDTH",
           "DEFAULT_HEIGHT"]