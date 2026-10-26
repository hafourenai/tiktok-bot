import re

from ._filter import apply_filters
from ._obj import Lexer, PdfSyntaxError, Ref, Stream, resolve

_OBJ_RE = re.compile(rb"(?<![0-9])(\d{1,10})\s+(\d{1,5})\s+obj\b")


class PdfDocument:
    """Random-access object store backed by a byte buffer."""

    def __init__(self, data: bytes):
        self.data = data
        self._cache: dict[tuple[int, int], object] = {}
        self._offsets: dict[int, int] = {}
        self._compressed: dict[int, tuple[int, int]] = {}  # num -> (objstm num, index)
        self._trailer: dict = {}
        self._scanned = False
        self.encrypted = False

    # -- public ------------------------------------------------------------
    def get_object(self, num: int, gen: int = 0):
        key = (num, gen)
        if key in self._cache:
            return self._cache[key]
        if (num, 0) in self._cache:
            return self._cache[(num, 0)]
        self._cache[key] = None  # cycle guard
        value = None
        try:
            value = self._load(num, gen)
        except Exception:
            value = None
        self._cache[key] = value
        return value

    def resolve(self, value):
        return resolve(value, self)

    def get(self, dictionary: dict, key: str, default=None):
        if not isinstance(dictionary, dict):
            return default
        if key not in dictionary:
            return default
        return self.resolve(dictionary[key])

    @property
    def trailer(self) -> dict:
        return self._trailer

    # -- loading -----------------------------------------------------------
    def _load(self, num: int, gen: int):
        offset = self._offsets.get(num)
        if offset is not None:
            value = self._parse_at(offset, num)
            if value is not _INVALID:
                return value
        located = self._compressed.get(num)
        if located is not None:
            value = self._load_from_objstm(located[0], located[1], num)
            if value is not _INVALID:
                return value
        if not self._scanned:
            self._brute_force_scan()
            if num in self._offsets:
                value = self._parse_at(self._offsets[num], num)
                if value is not _INVALID:
                    return value
            located = self._compressed.get(num)
            if located is not None:
                value = self._load_from_objstm(located[0], located[1], num)
                if value is not _INVALID:
                    return value
        return None

    def _parse_at(self, offset: int, expected: int | None):
        if offset < 0 or offset >= len(self.data):
            return _INVALID
        lexer = Lexer(self.data, offset, self)
        lexer.skip_space()
        start = lexer.pos
        num = lexer.read_number()
        if not isinstance(num, int):
            return _INVALID
        lexer.skip_space()
        gen = lexer.read_number()
        lexer.skip_space()
        if self.data[lexer.pos:lexer.pos + 3] != b"obj":
            return _INVALID
        lexer.pos += 3
        if expected is not None and num != expected:
            return _INVALID
        value = lexer.parse_object()
        if value is None and not self.data[lexer.pos:].strip():
            return None
        return value

    def _load_from_objstm(self, stm_num: int, index: int, expected: int):
        entries = self._objstm_entries(stm_num)
        if index >= len(entries):
            return _INVALID
        num, _offset = entries[index]
        if expected is not None and num != expected:
            # Index may be stale; find the right slot instead.
            for pos, (candidate, _offset) in enumerate(entries):
                if candidate == expected:
                    index, num = pos, candidate
                    break
            else:
                return _INVALID
        stream = self.get_object(stm_num, 0)
        if not isinstance(stream, Stream):
            return _INVALID
        try:
            payload = stream.data
        except Exception:
            return _INVALID
        pairs = entries
        if index + 1 < len(pairs):
            begin = pairs[index][1]
            stop = pairs[index + 1][1]
        else:
            begin = pairs[index][1]
            stop = len(payload)
        chunk = payload[begin:stop]
        lexer = Lexer(chunk, 0, self)
        try:
            return lexer.parse_object()
        except PdfSyntaxError:
            return _INVALID

    def _objstm_entries(self, stm_num: int):
        cached = getattr(self, "_objstm_cache", None)
        if cached is None:
            cached = self._objstm_cache = {}
        if stm_num in cached:
            return cached[stm_num]
        entries = []
        stream = self.get_object(stm_num, 0)
        if isinstance(stream, Stream):
            try:
                count = int(self.get(stream.dict, "N") or 0)
                first = int(self.get(stream.dict, "First") or 0)
                header = _decode(stream)[:first]
                lexer = Lexer(header, 0, self)
                for _ in range(count):
                    a = lexer.read_number()
                    lexer.skip_space()
                    b = lexer.read_number()
                    if not isinstance(a, int) or not isinstance(b, int):
                        break
                    entries.append((a, first + b))
            except Exception:
                entries = []
        cached[stm_num] = entries
        return entries

    # -- recovery ----------------------------------------------------------
    def _brute_force_scan(self) -> None:
        self._scanned = True
        for match in _OBJ_RE.finditer(self.data):
            num = int(match.group(1))
            if num in self._offsets:
                continue
            self._offsets[num] = match.start()
        # Second pass: register objects living inside object streams so that
        # containers we just found (usually the ObjStm itself) resolve.
        for num in list(self._offsets):
            value = self.get_object(num, 0)
            if isinstance(value, Stream) and self.get(value.dict, "Type") == "ObjStm":
                for pos, (child, _off) in enumerate(self._objstm_entries(num)):
                    self._compressed.setdefault(child, (num, pos))


def _decode(stream: Stream) -> bytes:
    try:
        return stream.data
    except Exception:
        return stream.rawdata


class _Invalid:
    __slots__ = ()


_INVALID = _Invalid()


class XrefParser:
    """Reads the xref chain starting from ``startxref``."""

    def __init__(self, doc: PdfDocument):
        self.doc = doc

    def read(self, data: bytes) -> dict:
        trailer = self._read_chain(data)
        if not trailer:
            trailer = self._read_trailer_by_scan(data)
        doc = self.doc
        doc._trailer = trailer or {}
        doc.encrypted = bool(doc._trailer.get("Encrypt"))
        return doc._trailer

    # -- chain -------------------------------------------------------------
    def _read_chain(self, data: bytes):
        start = self._find_startxref(data)
        trailer: dict = {}
        seen = set()
        hybrid_seen = set()
        while start is not None and start not in seen:
            seen.add(start)
            if not (0 <= start < len(data)):
                break
            section = self._read_section(data, start)
            if section is None:
                break
            entries, section_trailer = section
            for num, entry in entries.items():
                self._register(num, entry)
            if section_trailer.get("XRefStm") is not None:
                hybrid_seen.add(int(section_trailer["XRefStm"]))
            for key, value in section_trailer.items():
                trailer.setdefault(key, value)
            nxt = section_trailer.get("Prev")
            start = int(nxt) if isinstance(nxt, (int, float)) else None
        # Hybrid-reference files point at extra xref streams from the table.
        for offset in list(hybrid_seen):
            if offset in seen:
                continue
            seen.add(offset)
            section = self._read_section(data, offset)
            if section:
                entries, section_trailer = section
                for num, entry in entries.items():
                    self._register(num, entry)
                for key, value in section_trailer.items():
                    trailer.setdefault(key, value)
        return trailer

    def _register(self, num: int, entry) -> None:
        doc = self.doc
        kind = entry[0]
        if kind == 1:
            doc._offsets[num] = int(entry[1])
        elif kind == 2:
            existing = doc._compressed.get(num)
            if existing is None or existing[0] != int(entry[1]):
                doc._compressed[num] = (int(entry[1]), int(entry[2]))

    def _find_startxref(self, data: bytes) -> int | None:
        tail = data[-2048:]
        index = tail.rfind(b"startxref")
        if index < 0:
            return None
        lexer = Lexer(tail, index + 9, self.doc)
        lexer.skip_space()
        value = lexer.read_number()
        return int(value) if isinstance(value, int) else None

    def _read_section(self, data: bytes, offset: int):
        lexer = Lexer(data, offset, self.doc)
        lexer.skip_space()
        if data[lexer.pos:lexer.pos + 4] == b"xref":
            return self._read_table(lexer)
        lexer.skip_space()
        start = lexer.pos
        num = lexer.read_number()
        if isinstance(num, int):
            lexer.skip_space()
            gen = lexer.read_number()
            lexer.skip_space()
            if data[lexer.pos:lexer.pos + 3] == b"obj":
                value = lexer.parse_object()
                if isinstance(value, Stream):
                    return self._read_xref_stream(value)
        lexer.pos = start
        return None

    def _read_table(self, lexer: Lexer):
        doc = self.doc
        data = doc.data
        lexer.pos += 4  # consume 'xref'
        entries: dict[int, tuple] = {}
        while True:
            lexer.skip_space()
            if lexer.pos >= lexer.end:
                break
            if data[lexer.pos:lexer.pos + 7] == b"trailer":
                lexer.pos += 7
                trailer = lexer.parse_object()
                if not isinstance(trailer, dict):
                    trailer = {}
                # Some writers leave the array form behind; repair the dict.
                return entries, self._normalise_trailer(trailer)
            first = lexer.read_number()
            lexer.skip_space()
            count = lexer.read_number()
            if not isinstance(first, int) or not isinstance(count, int):
                break
            for i in range(count):
                lexer.skip_space()
                chunk = data[lexer.pos:lexer.pos + 20]
                parts = chunk.split()
                if len(parts) < 3:
                    lexer.pos += 20
                    continue
                try:
                    offset = int(parts[0])
                    gen = int(parts[1])
                    kind = parts[2]
                except ValueError:
                    lexer.pos += 20
                    continue
                if kind == b"n":
                    entries.setdefault(first + i, (1, offset, gen))
                elif kind == b"f":
                    entries.setdefault(first + i, (0, 0, gen))
                lexer.pos += 20
        return entries, {}

    def _read_xref_stream(self, stream: Stream):
        doc = self.doc
        try:
            payload = stream.data
        except Exception:
            payload = stream.rawdata
        entries: dict[int, tuple] = {}
        widths = doc.get(stream.dict, "W") or []
        try:
            widths = [int(w) for w in widths]
        except (TypeError, ValueError):
            widths = []
        size = int(doc.get(stream.dict, "Size") or 0)
        index = doc.get(stream.dict, "Index") or [0, size]
        index = [int(v) for v in index]
        if len(widths) < 3:
            widths = [1, 4, 2]
        row = sum(widths)
        pos = 0
        for pair in range(0, len(index) - 1, 2):
            start, count = index[pair], index[pair + 1]
            for i in range(count):
                if pos + row > len(payload):
                    break
                fields = []
                for width in widths:
                    if width == 0:
                        fields.append(None)
                    else:
                        fields.append(int.from_bytes(payload[pos:pos + width], "big"))
                        pos += width
                ftype = fields[0] if fields[0] is not None else 1
                obj_num = start + i
                if ftype == 1:
                    entries.setdefault(obj_num, (1, fields[1] or 0, fields[2] or 0))
                elif ftype == 2:
                    entries.setdefault(obj_num, (2, fields[1] or 0, fields[2] or 0))
        return entries, self._normalise_trailer(dict(stream.dict))

    def _normalise_trailer(self, trailer: dict) -> dict:
        out = {}
        for key, value in trailer.items():
            out[str(key)] = value
        # Filter arrays appear as /Filter [/FlateDecode]; keep as-is, the
        # filter stage handles both spellings.
        return out

    def _read_trailer_by_scan(self, data: bytes) -> dict:
        for match in re.finditer(rb"trailer", data):
            lexer = Lexer(data, match.end(), self.doc)
            value = lexer.parse_object()
            if isinstance(value, dict):
                return self._normalise_trailer(value)
        # Linearized files expose the dictionary through /Linearized; the
        # xref-stream path normally covers them, so this is only a last resort.
        index = data.rfind(b"/Root")
        if index > 0:
            lexer = Lexer(data, max(0, index - 8), self.doc)
            value = lexer.parse_object()
            if isinstance(value, dict):
                return self._normalise_trailer(value)
        return {}


def load(path_or_bytes) -> PdfDocument:
    """Build a :class:`PdfDocument` from a path or raw bytes."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        data = bytes(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as handle:
            data = handle.read()
    if not data:
        raise PdfSyntaxError("Berkas PDF kosong.")
    doc = PdfDocument(data)
    XrefParser(doc).read(data)
    return doc


__all__ = ["PdfDocument", "XrefParser", "load", "apply_filters", "Name", "Ref", "Stream"]
