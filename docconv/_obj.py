"""PDF lexer and object model (stage P1).

This is the foundation every later stage parses on top of: it turns raw PDF
bytes into Python objects (``dict``, ``list``, ``float``, ``int``, ``bytes``,
``bool``, ``None``) plus the two PDF-specific types ``Name``, ``Ref`` and
``Stream``.
"""

WHITESPACE = b"\x00\t\n\x0c\r "
DELIMITERS = b"()<>[]{}/%"
_REGULAR_END = WHITESPACE + DELIMITERS


class PdfSyntaxError(ValueError):
    """Raised when the byte stream cannot be interpreted as a PDF object."""


class Name(str):
    """A PDF name object (``/Foo``). Subclasses str for cheap comparisons."""

    __slots__ = ()

    def __repr__(self):  # pragma: no cover - debugging aid
        return "/" + str(self)


class Ref:
    """An indirect reference (``12 0 R``)."""

    __slots__ = ("num", "gen")

    def __init__(self, num: int, gen: int = 0):
        self.num = num
        self.gen = gen

    def __eq__(self, other):
        return isinstance(other, Ref) and (self.num, self.gen) == (other.num, other.gen)

    def __hash__(self):
        return hash((Ref, self.num, self.gen))

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"{self.num} {self.gen} R"


class Stream:
    """A stream object: a dictionary plus (still encoded) payload bytes."""

    __slots__ = ("dict", "rawdata", "_doc")

    def __init__(self, dictionary: dict, rawdata: bytes, doc=None):
        self.dict = dictionary
        self.rawdata = rawdata
        self._doc = doc

    def __contains__(self, key):
        return key in self.dict

    def __getitem__(self, key):
        return self.dict[key]

    def get(self, key, default=None):
        return self.dict.get(key, default)

    @property
    def doc(self):
        return self._doc

    @property
    def data(self) -> bytes:
        """Decoded payload. Requires the owning document for filter state."""
        from ._filter import apply_filters

        return apply_filters(self, self._doc)


class Keyword(str):
    """A bare keyword token (``obj``, ``endobj``, ``stream``, operator)."""

    __slots__ = ()


_HEXDIGITS = b"0123456789abcdefABCDEF"


def _is_white(byte: int) -> bool:
    return byte in WHITESPACE


def _is_delim(byte: int) -> bool:
    return byte in DELIMITERS


def _is_regular(byte: int) -> bool:
    return byte not in _REGULAR_END


class Lexer:
    """Byte-level cursor over PDF syntax.

    The lexer is deliberately tolerant: broken producers are common, so every
    method degrades to "best effort" rather than raising, except where a value
    is structurally required.
    """

    def __init__(self, data: bytes, pos: int = 0, doc=None):
        self.data = data
        self.pos = pos
        self.doc = doc
        self.end = len(data)

    # -- low level ---------------------------------------------------------
    def skip_space(self) -> None:
        """Advance past whitespace and ``%`` comments."""
        data, end = self.data, self.end
        pos = self.pos
        while pos < end:
            byte = data[pos]
            if byte in WHITESPACE:
                pos += 1
            elif byte == 0x25:  # '%'
                while pos < end and data[pos] not in b"\r\n":
                    pos += 1
            else:
                break
        self.pos = pos

    def at_end(self) -> bool:
        self.skip_space()
        return self.pos >= self.end

    def peek_byte(self) -> int:
        return self.data[self.pos] if self.pos < self.end else -1

    def next_byte(self) -> int:
        if self.pos >= self.end:
            return -1
        self.pos += 1
        return self.data[self.pos - 1]

    def read_keyword(self) -> str:
        start = self.pos
        data, end = self.data, self.end
        pos = start
        while pos < end and _is_regular(data[pos]):
            pos += 1
        self.pos = pos
        return data[start:pos].decode("latin-1")

    def expect_keyword(self, word: str) -> bool:
        self.skip_space()
        start = self.pos
        if self.data[start:start + len(word)] == word.encode("latin-1"):
            self.pos = start + len(word)
            return True
        return False

    # -- scalars -----------------------------------------------------------
    def read_name(self) -> Name:
        # self.pos points at '/'
        self.pos += 1
        data, end = self.data, self.end
        pos = self.pos
        out = bytearray()
        while pos < end and _is_regular(data[pos]):
            byte = data[pos]
            if byte == 0x23 and pos + 2 < end:  # '#'
                hi, lo = data[pos + 1], data[pos + 2]
                if hi in _HEXDIGITS and lo in _HEXDIGITS:
                    out.append(int(data[pos + 1:pos + 3], 16))
                    pos += 3
                    continue
            out.append(byte)
            pos += 1
        self.pos = pos
        return Name(out.decode("latin-1"))

    def read_literal_string(self) -> bytes:
        # self.pos points at '('
        self.pos += 1
        data, end = self.data, self.end
        pos = self.pos
        out = bytearray()
        depth = 1
        while pos < end:
            byte = data[pos]
            if byte == 0x5C:  # backslash
                pos += 1
                if pos >= end:
                    break
                esc = data[pos]
                if esc in b"nrtbf":
                    out.append({0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}[esc])
                    pos += 1
                elif esc in b"01234567":
                    digits = bytearray()
                    while pos < end and len(digits) < 3 and data[pos] in b"01234567":
                        digits.append(data[pos])
                        pos += 1
                    out.append(int(digits, 8) & 0xFF)
                elif esc == 0x0A:
                    pos += 1  # line continuation
                elif esc == 0x0D:
                    pos += 1
                    if pos < end and data[pos] == 0x0A:
                        pos += 1
                else:
                    out.append(esc)
                    pos += 1
                continue
            if byte == 0x28:  # '('
                depth += 1
                out.append(byte)
            elif byte == 0x29:  # ')'
                depth -= 1
                if depth == 0:
                    pos += 1
                    break
                out.append(byte)
            else:
                out.append(byte)
            pos += 1
        self.pos = pos
        return bytes(out)

    def read_hex_string(self) -> bytes:
        # self.pos points at '<'
        self.pos += 1
        data, end = self.data, self.end
        pos = self.pos
        digits = bytearray()
        while pos < end and data[pos] != 0x3E:
            byte = data[pos]
            if byte in _HEXDIGITS:
                digits.append(byte)
            pos += 1
        self.pos = min(pos + 1, end)
        if len(digits) % 2:
            digits.append(0x30)  # trailing nibble is 0
        try:
            return bytes.fromhex(digits.decode("ascii"))
        except ValueError:  # pragma: no cover - defensive
            return b""

    def read_number(self):
        start = self.pos
        data, end = self.data, self.end
        pos = start
        while pos < end and _is_regular(data[pos]):
            pos += 1
        self.pos = pos
        token = data[start:pos]
        try:
            if b"." in token or b"e" in token or b"E" in token:
                return float(token.replace(b"--", b"-"))
            return int(token)
        except ValueError:
            return 0

    def _peek_is_reference(self, first: int) -> Ref | None:
        """After an integer, check for ``<int> R`` without consuming on failure."""
        save = self.pos
        self.skip_space()
        if not (self.pos < self.end and (0x30 <= self.data[self.pos] <= 0x39 or self.data[self.pos] in b"+-.")):
            self.pos = save
            return None
        second_start = self.pos
        second = self.read_number()
        self.skip_space()
        if isinstance(second, int) and self.pos < self.end and self.data[self.pos] == 0x52:
            after = self.pos + 1
            if after >= self.end or not _is_regular(self.data[after]):
                self.pos = after
                return Ref(first, second)
        self.pos = save if save != second_start else second_start
        return None

    # -- composites --------------------------------------------------------
    def read_array(self) -> list:
        self.pos += 1  # consume '['
        out = []
        while True:
            self.skip_space()
            if self.pos >= self.end:
                break
            byte = self.data[self.pos]
            if byte == 0x5D:  # ']'
                self.pos += 1
                break
            if byte == 0x3E and self.data[self.pos:self.pos + 2] == b">>":
                self.pos += 2
                break
            before = self.pos
            item = self.parse_object(depth=1)
            if self.pos == before:
                self.pos += 1
                continue
            if item is not _SKIP:
                out.append(item)
        return out

    def read_dict(self) -> dict:
        self.pos += 2  # consume '<<'
        out = {}
        while True:
            self.skip_space()
            if self.pos >= self.end:
                break
            if self.data[self.pos:self.pos + 2] == b">>":
                self.pos += 2
                break
            if self.data[self.pos] != 0x2F:
                before = self.pos
                stray = self.parse_object(depth=1)
                if self.pos == before:
                    self.pos += 1
                if stray is not _SKIP:
                    out[_stray_key(stray)] = None
                continue
            key = self.read_name()
            value = self.parse_object(depth=1)
            if value is _SKIP:
                value = None
            out[str(key)] = value
        return out

    def parse_object(self, depth: int = 0):
        """Parse one object at the cursor."""
        self.skip_space()
        if self.pos >= self.end:
            return None
        data = self.data
        byte = data[self.pos]
        if byte == 0x2F:
            return self.read_name()
        if byte == 0x28:
            return self.read_literal_string()
        if byte == 0x5B:
            return self.read_array()
        if byte == 0x3C:
            if data[self.pos:self.pos + 2] == b"<<":
                dictionary = self.read_dict()
                self.skip_space()
                if data[self.pos:self.pos + 6] == b"stream":
                    return self._read_stream_body(dictionary)
                return dictionary
            return self.read_hex_string()
        if byte == 0x5D or byte == 0x3E:  # stray closer
            self.pos += 1
            return _SKIP
        if byte in b"{}":
            self.pos += 1
            return _SKIP
        if (0x30 <= byte <= 0x39) or byte in b"+-.":
            value = self.read_number()
            if isinstance(value, int):
                ref = self._peek_is_reference(value)
                if ref is not None:
                    return ref
            return value
        if byte == 0x7B:  # '{' PostScript function body - skip to matching '}'
            depth_ps = 0
            while self.pos < self.end:
                if data[self.pos] == 0x7B:
                    depth_ps += 1
                elif data[self.pos] == 0x7D:
                    depth_ps -= 1
                    if depth_ps == 0:
                        self.pos += 1
                        break
                self.pos += 1
            return _SKIP
        word = self.read_keyword()
        if not word:
            self.pos += 1
            return _SKIP
        if word == "true":
            return True
        if word == "false":
            return False
        if word == "null":
            return None
        return Keyword(word)

    def _read_stream_body(self, dictionary: dict) -> Stream:
        data = self.data
        self.pos += 6  # consume 'stream'
        if data[self.pos:self.pos + 2] == b"\r\n":
            self.pos += 2
        elif self.pos < self.end and data[self.pos] in b"\n\r":
            self.pos += 1
        start = self.pos
        length = dictionary.get("Length")
        end = None
        if isinstance(length, int) and length >= 0:
            candidate = start + length
            probe = candidate
            # Tolerate writers that put trailing whitespace before 'endstream'.
            while probe < self.end and data[probe] in b"\r\n\x20":
                probe += 1
            if data[probe:probe + 9] == b"endstream" and probe >= start:
                end = candidate
        if end is None:
            found = data.find(b"endstream", start)
            if found < 0:
                found = self.end
            end = found
            # Trim the EOL that precedes 'endstream'.
            while end > start and data[end - 1] in b"\r\n":
                end -= 1
        raw = data[start:end]
        after = data.find(b"endstream", end)
        self.pos = (after + 9) if after >= 0 else end
        return Stream(dictionary, raw, self.doc)


class _Skip:
    __slots__ = ()

    def __repr__(self):  # pragma: no cover - debugging aid
        return "<skip>"


_SKIP = _Skip()
SKIP = _SKIP


def _stray_key(value) -> str:
    if isinstance(value, Keyword):
        return str(value)
    if isinstance(value, (Ref, Name)):
        return str(value)
    return repr(value)


def resolve(value, doc):
    """Follow ``Ref`` chains until a direct object is reached."""
    seen = 0
    while isinstance(value, Ref) and doc is not None and seen < 64:
        value = doc.get_object(value.num, value.gen)
        seen += 1
    return value


def tokenize_operators(data: bytes):
    """Yield ``('obj', value)`` / ``('op', keyword)`` pairs for a content stream.

    Used by :mod:`docconv._content`; kept here so the lexer rules live in one
    place.
    """
    lexer = Lexer(data, 0, None)
    end = lexer.end
    while lexer.pos < end:
        lexer.skip_space()
        if lexer.pos >= end:
            break
        byte = data[lexer.pos]
        start = lexer.pos
        if byte == 0x2F:
            yield ("obj", lexer.read_name())
            continue
        if byte == 0x28:
            yield ("obj", lexer.read_literal_string())
            continue
        if byte == 0x3C:
            if data[lexer.pos:lexer.pos + 2] == b"<<":
                lexer.pos += 2
                yield ("obj", _SKIP)  # inline dict: content streams never use them
                continue
            yield ("obj", lexer.read_hex_string())
            continue
        if byte == 0x5B:
            yield ("obj", lexer.read_array())
            continue
        if (0x30 <= byte <= 0x39) or byte in b"+-.":
            value = lexer.read_number()
            if isinstance(value, int):
                save = lexer.pos
                lexer.skip_space()
                if lexer.pos < end and (0x30 <= data[lexer.pos] <= 0x39 or data[lexer.pos] in b"+-."):
                    value2 = lexer.read_number()
                    lexer.skip_space()
                    if isinstance(value2, int) and data[lexer.pos:lexer.pos + 1] == b"R":
                        lexer.pos += 1
                        yield ("obj", Ref(value, value2))
                        continue
                lexer.pos = save
            yield ("obj", value)
            continue
        if byte == 0x5D or byte == 0x3E or byte in b"{}":
            lexer.pos += 1
            continue
        word = lexer.read_keyword()
        if not word:
            lexer.pos = start + 1
            continue
        yield ("op", word)