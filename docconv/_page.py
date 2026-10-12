"""Document structure and page tree (stage P4)."""

from ._obj import PdfSyntaxError, Stream
from ._xref import load

DEFAULT_MEDIABOX = (0.0, 0.0, 612.0, 792.0)


class PdfEncryptedError(PdfSyntaxError):
    """Raised for encrypted PDFs, which this reader cannot open yet."""


class Page:
    """One page: resolved attributes plus lazily decoded content."""

    __slots__ = ("doc", "dict", "number", "mediabox", "cropbox", "resources",
                 "rotate", "annotations", "_content_cache")

    def __init__(self, doc, dictionary: dict, number: int):
        self.doc = doc
        self.dict = dictionary
        self.number = number
        self.mediabox = DEFAULT_MEDIABOX
        self.cropbox = None
        self.resources = {}
        self.rotate = 0
        self.annotations = []
        self._content_cache = None

    @property
    def width(self) -> float:
        return abs(self.mediabox[2] - self.mediabox[0])

    @property
    def height(self) -> float:
        return abs(self.mediabox[3] - self.mediabox[1])

    def content_bytes(self) -> bytes:
        """Concatenated, decoded content stream of the page."""
        if self._content_cache is not None:
            return self._content_cache
        doc = self.doc
        source = doc.get(self.dict, "Contents")
        chunks: list[bytes] = []
        for item in source if isinstance(source, list) else [source]:
            if item is None:
                continue
            value = doc.resolve(item)
            if isinstance(value, Stream):
                try:
                    chunks.append(value.data)
                except Exception:
                    continue
        data = b"\n".join(chunks)
        self._content_cache = data
        return data

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<Page {self.number} {self.width:.0f}x{self.height:.0f}>"


class Document:
    """A parsed PDF, exposing an ordered list of :class:`Page`."""

    def __init__(self, data: bytes):
        self.raw = data
        self.doc = load(data)
        if self.doc.encrypted:
            raise PdfEncryptedError(
                "PDF ini terenkripsi. Hapus proteksi kata sandi terlebih dahulu "
                "sebelum dikonversi."
            )
        self.pages = self._build_pages()

    def __len__(self):
        return len(self.pages)

    # -- internals ---------------------------------------------------------
    def _build_pages(self):
        doc = self.doc
        trailer = doc.trailer
        root = doc.get(trailer, "Root")
        if not isinstance(root, dict):
            root = self._find_root_by_scan()
        pages_ref = doc.get(root, "Pages") if isinstance(root, dict) else None
        pages: list[Page] = []
        seen = set()
        if isinstance(pages_ref, dict):
            self._walk(pages_ref, {}, pages, seen, 0)
        if not pages:
            # Fallback: treat every /Type /Page object as a page, ordered by
            # object number (matches what most viewers show for broken files).
            for num in sorted(doc._offsets):
                value = doc.get_object(num, 0)
                if isinstance(value, dict) and value.get("Type") == "Page":
                    self._finalise(value, pages, {}, 0)
        return pages

    def _find_root_by_scan(self):
        doc = self.doc
        for num in sorted(doc._offsets):
            value = doc.get_object(num, 0)
            if isinstance(value, dict) and value.get("Type") == "Catalog":
                return value
        return {}

    def _walk(self, node: dict, inherited: dict, out: list, seen: set, depth: int) -> None:
        if depth > 64 or len(out) > 5000:
            return
        merged = dict(inherited)
        for key in ("Resources", "MediaBox", "CropBox", "Rotate"):
            if key in node:
                merged[key] = node[key]
        node_type = self.doc.get(node, "Type")
        kids = self.doc.get(node, "Kids")
        if node_type == "Page" or (kids is None and "Contents" in node):
            self._finalise(node, out, merged, {})
            return
        if not isinstance(kids, list):
            self._finalise(node, out, merged, {})
            return
        for kid in kids:
            key = (kid.num, kid.gen) if hasattr(kid, "num") else id(kid)
            if key in seen:
                continue
            seen.add(key)
            resolved = self.doc.resolve(kid)
            if isinstance(resolved, dict):
                self._walk(resolved, merged, out, seen, depth + 1)

    def _finalise(self, node: dict, out: list, inherited: dict, _depth=0) -> None:
        doc = self.doc
        page = Page(doc, node, len(out) + 1)
        resources = node.get("Resources", inherited.get("Resources"))
        resources = doc.resolve(resources)
        page.resources = resources if isinstance(resources, dict) else {}
        box = node.get("MediaBox", inherited.get("MediaBox"))
        page.mediabox = _normalise_box(doc.resolve(box)) or DEFAULT_MEDIABOX
        crop = node.get("CropBox", inherited.get("CropBox"))
        cropbox = _normalise_box(doc.resolve(crop))
        if cropbox:
            page.cropbox = cropbox
        rotate = node.get("Rotate", inherited.get("Rotate"))
        try:
            page.rotate = (int(doc.resolve(rotate)) // 90) * 90 % 360
        except (TypeError, ValueError):
            page.rotate = 0
        annots = doc.get(node, "Annots")
        page.annotations = annots if isinstance(annots, list) else []
        out.append(page)


def _normalise_box(box):
    """Return an (x0, y0, x1, y1) float tuple with ordered corners, or None."""
    if not isinstance(box, list) or len(box) != 4:
        return None
    try:
        values = [float(v) for v in box]
    except (TypeError, ValueError):
        return None
    x0, x1 = sorted((values[0], values[2]))
    y0, y1 = sorted((values[1], values[3]))
    if x1 - x0 < 1e-6 or y1 - y0 < 1e-6:
        return None
    return (x0, y0, x1, y1)


def load_document(path_or_bytes) -> Document:
    if isinstance(path_or_bytes, (bytes, bytearray)):
        return Document(bytes(path_or_bytes))
    with open(path_or_bytes, "rb") as handle:
        return Document(handle.read())


__all__ = ["Document", "Page", "load_document", "PdfEncryptedError"]