"""OOXML package utilities for Word/Excel/PowerPoint formats.

Handles ZIP structure, XML parts, and relationships using only stdlib.
"""

import zipfile
from xml.etree import ElementTree

# The zipfile module only recognises these compression constants.
ZIP_DEFLATED = zipfile.ZIP_DEFLATED
ZIP_STORED = zipfile.ZIP_STORED

CONTENT_TYPES = "[Content_Types].xml"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


class OoxmlError(ValueError):
    """Raised for malformed or unsupported OOXML packages."""


# -- XML helpers ----------------------------------------------------------
def parse_xml(data: bytes) -> ElementTree.Element:
    """Parse an XML part, tolerating the odd stray byte real files contain."""
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError:
        # Some producers emit a stray NUL or undeclared encoding on the
        # declaration. Stripping control chars is enough to recover.
        cleaned = bytes(b for b in data if b >= 9 or b in (9, 10, 13))
        cleaned = cleaned.replace(b"\x00", b"")
        return ElementTree.fromstring(cleaned)


def local_name(tag: str) -> str:
    """Namespace-insensitive tag name ('{ns}p' -> 'p')."""
    if isinstance(tag, str) and tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag if isinstance(tag, str) else ""


def find_all(element, name: str):
    """Iterate descendants (and ``element`` itself) whose local name matches."""
    if local_name(element.tag) == name:
        yield element
    for child in element.iter():
        if child is not element and local_name(child.tag) == name:
            yield child


def text_of(element, name: str, default: str = "") -> str:
    """Concatenated text of the first descendant named ``name``."""
    for candidate in find_all(element, name):
        parts = [node.text or "" for node in candidate.iter()]
        return "".join(parts)
    return default


def descendants(element, name: str) -> list:
    return [node for node in element.iter()
            if node is not element and local_name(node.tag) == name]


# -- package writer -------------------------------------------------------
class PackageWriter:
    """Builds an OOXML ZIP package."""

    def __init__(self, compression: int = ZIP_DEFLATED):
        self.parts: dict[str, bytes] = {}
        self.compression = compression

    def set(self, name: str, data) -> None:
        """Add or replace a part. ``data`` may be str or bytes."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.parts[name] = data

    def set_xml(self, name: str, root: ElementTree.Element) -> None:
        self.parts[name] = ElementTree.tostring(
            root, encoding="utf-8", xml_declaration=True)

    def has(self, name: str) -> bool:
        return name in self.parts

    def write(self, path, content_types: str) -> str:
        """Write the ZIP with the given ``[Content_Types].xml`` content."""
        self.parts[CONTENT_TYPES] = content_types.encode("utf-8")
        with zipfile.ZipFile(path, "w", self.compression) as archive:
            # [Content_Types].xml must be the first entry by convention.
            archive.writestr(CONTENT_TYPES, self.parts[CONTENT_TYPES])
            for name, data in self.parts.items():
                if name == CONTENT_TYPES:
                    continue
                archive.writestr(name, data)
        return str(path)


def rels_xml(relationships) -> str:
    """Serialise a relationships part.

    ``relationships`` is an iterable of ``(id, type_suffix, target[, mode])``
    where ``type_suffix`` is the last segment of the relationship type URI.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             f'<Relationships xmlns="{RELS_NS}">']
    for entry in relationships:
        rid, kind, target = entry[0], entry[1], entry[2]
        mode = entry[3] if len(entry) > 3 else None
        mode_attr = f' TargetMode="{mode}"' if mode else ""
        lines.append(
            f'<Relationship Id="{rid}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{kind}" '
            f'Target="{target}"{mode_attr}/>'
        )
    lines.append("</Relationships>")
    return "".join(lines)


DEFAULT_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '</Types>'
)


def content_types_xml(overrides) -> str:
    """Build ``[Content_Types].xml`` with per-part overrides.

    ``overrides`` is an iterable of ``(part_name, content_type)``.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             f'<Types xmlns="{CONTENT_TYPES_NS}">',
             '<Default Extension="rels" '
             'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
             '<Default Extension="xml" ContentType="application/xml"/>']
    for name, content_type in overrides:
        lines.append(f'<Override PartName="{name}" ContentType="{content_type}"/>')
    lines.append("</Types>")
    return "".join(lines)


# -- package reader -------------------------------------------------------
class PackageReader:
    """Reads an OOXML ZIP package."""

    def __init__(self, path):
        try:
            self.archive = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError) as exc:
            raise OoxmlError(f"Berkas bukan paket Office yang valid: {exc}") from exc

    def close(self) -> None:
        self.archive.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def names(self) -> list:
        return self.archive.namelist()

    def has(self, name: str) -> bool:
        return name in self.archive.namelist()

    def read(self, name: str) -> bytes:
        try:
            return self.archive.read(name)
        except KeyError as exc:
            raise OoxmlError(f"Part tidak ditemukan: {name}") from exc

    def xml(self, name: str):
        return parse_xml(self.read(name))

    def relationships(self, part: str) -> dict:
        """Return ``{rId: (kind, target)}`` for a part's ``_rels`` file."""
        base = part.rsplit("/", 1)
        folder = f"{base[0]}/_rels/" if len(base) == 2 else "_rels/"
        name = f"{folder}{base[-1]}.rels"
        if not self.has(name):
            return {}
        out = {}
        for relationship in self.xml(name).iter():
            if local_name(relationship.tag) != "Relationship":
                continue
            rid = relationship.get("Id")
            kind = relationship.get("Type", "").rsplit("/", 1)[-1]
            out[rid] = (kind, relationship.get("Target", ""))
        return out

    def resolve_target(self, part: str, target: str) -> str:
        """Resolve a relationship target relative to the part that declares it."""
        if target.startswith("/"):
            return target.lstrip("/")
        base = part.rsplit("/", 1)[0] if "/" in part else ""
        segments = base.split("/") if base else []
        for piece in target.split("/"):
            if piece in ("", "."):
                continue
            if piece == "..":
                if segments:
                    segments.pop()
                continue
            segments.append(piece)
        return "/".join(segments)


__all__ = ["PackageWriter", "PackageReader", "rels_xml", "content_types_xml",
           "DEFAULT_CONTENT_TYPES", "parse_xml", "local_name", "find_all",
           "text_of", "descendants", "OoxmlError", "ZIP_DEFLATED", "ZIP_STORED"]