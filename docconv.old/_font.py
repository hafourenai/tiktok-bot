from ._obj import Stream, tokenize_operators

# -- base encodings ------------------------------------------------------
# StandardEncoding and WinAnsiEncoding are built from Python's own codecs so
# there is a single source of truth rather than a hand-typed table.
_STANDARD_BASE = {
    # code: glyph name (only entries that differ from Latin-1 need listing)
    39: "quotesingle", 96: "grave", 164: "currency",
    166: "brokenbar", 169: "copyright", 170: "registered",
    172: "logicalnot", 174: "registered", 183: "middot",
    200: "Eth", 202: "florin", 203: "guillemotleft",
    208: "currency", 234: "guillemotright", 235: "questiondown",
    240: "perthousand", 241: "germandbls", 242: "guilsinglleft",
    243: "guilsinglright", 245: "fi", 246: "fl",
    247: "dotlessi", 248: "dieresis", 253: "breve",
    254: "macron", 255: "dotaccent",
}

GLYPH_TO_UNICODE = {
    "space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#",
    "dollar": "$", "percent": "%", "ampersand": "&", "quotesingle": "'",
    "quoteright": "’", "quoteleft": "‘", "parenleft": "(",
    "parenright": ")", "asterisk": "*", "plus": "+", "comma": ",",
    "hyphen": "-", "period": ".", "slash": "/", "zero": "0", "one": "1",
    "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "colon": ":", "semicolon": ";",
    "less": "<", "equal": "=", "greater": ">", "question": "?",
    "at": "@", "bracketleft": "[", "backslash": "\\", "bracketright": "]",
    "asciicircum": "^", "underscore": "_", "grave": "`", "braceleft": "{",
    "bar": "|", "braceright": "}", "asciitilde": "~", "endash": "–",
    "emdash": "—", "bullet": "•", "quotedblleft": "“",
    "quotedblright": "”", "quotesinglbase": "‚", "quotedblbase": "„",
    "dagger": "†", "daggerdbl": "‡", "ellipsis": "…",
    "perthousand": "‰", "guilsinglleft": "‹",
    "guilsinglright": "›", "trademark": "™", "fi": "fi",
    "fl": "fl", "Euro": "€", "euro": "€",
    "nbspace": " ", "minus": "−",
    "ID": "",  # filler key kept out of lookups
}

_MACROMAN_HIGH = {
    128: "Ä", 129: "Å", 130: "Ç", 131: "É", 132: "Ñ",
    133: "Ö", 134: "Ü", 135: "á", 136: "à", 137: "â",
    138: "ä", 139: "ã", 140: "å", 141: "ç", 142: "é",
    143: "è", 144: "ê", 145: "ë", 146: "í", 147: "ì",
    148: "î", 149: "ï", 150: "ñ", 151: "ó", 152: "ò",
    153: "ô", 154: "ö", 155: "õ", 156: "ú", 157: "ù",
    158: "û", 159: "ü", 160: "†", 161: "°", 162: "¢",
    163: "£", 164: "§", 165: "•", 166: "¶", 167: "ß",
    168: "®", 169: "©", 170: "™", 171: "´", 172: "¨",
    174: "Æ", 175: "Ø", 177: "±", 180: "¥", 181: "µ",
    187: "ª", 188: "º", 190: "æ", 191: "ø", 192: "¿",
    193: "¡", 194: "¬", 196: "ƒ", 199: "«", 200: "»",
    201: "…", 202: " ", 203: "À", 204: "Ã", 205: "Õ",
    206: "Œ", 207: "œ", 208: "–", 209: "—", 210: "“",
    211: "”", 212: "‘", 213: "’", 214: "÷", 216: "ÿ",
    217: "Ÿ", 218: "⁄", 219: "€", 220: "‹", 221: "›",
    222: "ﬁ", 223: "ﬂ", 224: "‡", 225: "·", 226: "‚",
    227: "„", 228: "‰", 229: "Â", 230: "Ê", 231: "Á",
    232: "Ë", 233: "È", 234: "Í", 235: "Î", 236: "Ï",
    237: "Ì", 238: "Ó", 239: "Ô", 241: "Ò", 242: "Ú",
    243: "Û", 244: "Ù", 245: "ı", 246: "ˆ", 247: "˜",
    248: "¯", 249: "˘", 250: "˙", 251: "˚", 252: "¸",
    253: "˝", 254: "˛", 255: "ˇ",
}


def _build_from_codec(codec: str, skip: set) -> dict:
    table = {}
    for code in range(32, 256):
        try:
            char = bytes([code]).decode(codec)
        except UnicodeDecodeError:
            continue
        if code in skip:
            continue
        table[code] = char
    return table


STANDARD_ENCODING = _build_from_codec("latin-1", set(_STANDARD_BASE))
for _code, _name in _STANDARD_BASE.items():
    STANDARD_ENCODING.setdefault(_code, GLYPH_TO_UNICODE.get(_name, ""))

WIN_ANSI = _build_from_codec("cp1252", set())
# cp1252 assigns characters at 0x80-0x9F too; only these five are undefined.
for _code in (0x81, 0x8D, 0x8F, 0x90, 0x9D):
    WIN_ANSI[_code] = ""
MAC_ROMAN = _build_from_codec("mac_roman", set())


def _glyph_name_to_unicode(name: str) -> str:
    if not name:
        return ""
    if name in GLYPH_TO_UNICODE:
        return GLYPH_TO_UNICODE[name]
    if "." in name:
        return _glyph_name_to_unicode(name.split(".")[-1])
    if len(name) == 1:
        return name
    match = _uni_pattern(name)
    if match:
        return chr(int(match.group(1), 16))
    # "g123"/"cid123" style names from subset fonts.
    digits = ""
    for ch in name:
        if ch.isdigit():
            digits += ch
        else:
            digits = ""
            break
    if digits and digits[0] != "0":
        try:
            return chr(int(digits))
        except ValueError:
            return ""
    return ""


import re as _re

_uni_pattern = _re.compile(r"^uni([0-9A-Fa-f]{4,6})$")
_u_pattern = _re.compile(r"^u([0-9A-Fa-f]{4,6})$")


class Font:
    """A PDF font, able to decode byte strings into text plus widths."""

    __slots__ = ("dict", "doc", "subtype", "base_encoding", "differences",
                 "to_unicode", "widths", "default_width", "two_byte",
                 "cid_default_width", "cid_widths", "standard_widths",
                 "_cache", "warnings")

    def __init__(self, dictionary: dict, doc):
        self.dict = dictionary
        self.doc = doc
        self.subtype = str(doc.get(dictionary, "Subtype") or "")
        self.base_encoding = self._load_base_encoding()
        self.differences = self._load_differences()
        self.to_unicode = self._load_to_unicode()
        self.two_byte = self.subtype == "Type0"
        self.widths = None
        self.default_width = 500.0
        self.cid_widths = None
        self.cid_default_width = 1000.0
        self.standard_widths = None
        self._cache = {}
        self.warnings = []
        self._load_widths()

    # -- construction helpers ---------------------------------------------
    def _load_base_encoding(self) -> dict:
        base = WIN_ANSI
        name = self.doc.get(self.dict, "Encoding")
        if isinstance(name, Stream):
            name = self.doc.get(name.dict, "BaseEncoding")
        name = str(name or "")
        if name in ("WinAnsiEncoding", ""):
            base = dict(WIN_ANSI)
        elif name == "MacRomanEncoding":
            base = dict(MAC_ROMAN)
        elif name == "StandardEncoding":
            base = dict(STANDARD_ENCODING)
        else:
            # Symbolic fonts often lack /Encoding but ship glyph names.
            base = dict(STANDARD_ENCODING)
        return base

    def _load_differences(self) -> dict:
        out: dict[int, str] = {}
        encoding = self.doc.get(self.dict, "Encoding")
        if not isinstance(encoding, dict):
            return out
        differences = self.doc.get(encoding, "Differences")
        if not isinstance(differences, list):
            return out
        code = 0
        for item in differences:
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                code = int(item)
            elif isinstance(item, str):
                out[code] = str(item)
                code += 1
        return out

    def _load_to_unicode(self):
        stream = self.doc.get(self.dict, "ToUnicode")
        if not isinstance(stream, Stream):
            return None
        try:
            payload = stream.data
        except Exception:
            return None
        return parse_tounicode(payload)

    def _load_widths(self) -> None:
        doc = self.doc
        if self.two_byte:
            descendants = doc.get(self.dict, "DescendantFonts")
            descendant = None
            if isinstance(descendants, list) and descendants:
                descendant = doc.resolve(descendants[0])
            if isinstance(descendant, dict):
                self.cid_default_width = _num(doc.get(descendant, "DW"), 1000.0)
                self.cid_widths = doc.get(descendant, "W")
            return
        first = doc.get(self.dict, "FirstChar")
        widths = doc.get(self.dict, "Widths")
        if isinstance(widths, list) and widths:
            start = int(_num(first, 0))
            self.widths = {}
            for offset, value in enumerate(widths):
                resolved = doc.resolve(value)
                if isinstance(resolved, (int, float)) and not isinstance(resolved, bool):
                    self.widths[start + offset] = float(resolved)
        base = str(doc.get(self.dict, "BaseFont") or "")
        self.standard_widths = _BASE14_WIDTHS.get(_base14_key(base))
        descriptor = doc.get(self.dict, "FontDescriptor")
        if self.standard_widths is None and isinstance(descriptor, dict):
            missing = doc.get(descriptor, "MissingWidth")
            if isinstance(missing, (int, float)) and not isinstance(missing, bool):
                self.default_width = float(missing)

    # -- public ------------------------------------------------------------
    def char_width(self, code: int) -> float:
        """Advance width in 1/1000 text-space units."""
        if self.two_byte:
            widths = self.cid_widths
            if isinstance(widths, list):
                index = 0
                while index < len(widths):
                    first = self.doc.resolve(widths[index])
                    if index + 1 < len(widths) and isinstance(
                        self.doc.resolve(widths[index + 1]), list
                    ):
                        # Form 1: c [w1 w2 ... wn]
                        array = self.doc.resolve(widths[index + 1])
                        position = int(_num(first, 0))
                        if isinstance(array, list):
                            for offset, item in enumerate(array):
                                if position + offset == code:
                                    return _num(self.doc.resolve(item), self.cid_default_width)
                        index += 2
                        continue
                    if index + 2 >= len(widths):
                        break
                    last = self.doc.resolve(widths[index + 1])
                    value = _num(self.doc.resolve(widths[index + 2]), self.cid_default_width)
                    start_code = int(_num(first, 0))
                    end_code = int(_num(last, start_code))
                    if start_code <= code <= end_code:
                        return value
                    index += 3
            return self.cid_default_width
        if self.widths is not None:
            width = self.widths.get(code)
            if width is not None:
                return width
            return self.default_width
        table = self.standard_widths
        if table is None:
            return self.default_width
        ascii_char = self.decode_single(code)
        if ascii_char and len(ascii_char) == 1 and ord(ascii_char[0]) < 256:
            return table.get(ord(ascii_char[0]), 500.0)
        return 500.0

    def decode_single(self, code: int) -> str:
        """Map one character code to a string (usually length 1)."""
        cached = self._cache.get(code)
        if cached is not None:
            return cached
        text = ""
        if self.two_byte:
            if self.to_unicode and code in self.to_unicode:
                text = self.to_unicode[code]
            else:
                # Identity-H without ToUnicode: not recoverable. Record once.
                if code not in self._cache and not self.warnings:
                    self.warnings.append(
                        "Font subset tanpa /ToUnicode; sebagian glyph tidak dapat dipetakan."
                    )
                text = ""
        else:
            if self.to_unicode and code in self.to_unicode:
                text = self.to_unicode[code]
            elif code in self.differences:
                text = _glyph_name_to_unicode(self.differences[code])
            else:
                text = self.base_encoding.get(code, "")
        self._cache[code] = text
        return text

    def decode(self, raw: bytes):
        """Decode a PDF string into ``[(text, code), ...]``.

        Spaces are preserved explicitly so the layout stage can rebuild word
        gaps from coordinates instead of trusting the string contents.
        """
        pieces = []
        if self.two_byte:
            codes = [int.from_bytes(raw[i:i + 2], "big") for i in range(0, len(raw) - 1, 2)]
        else:
            codes = list(raw)
        for code in codes:
            text = self.decode_single(code)
            pieces.append((text, code))
        return pieces

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<Font {self.doc.get(self.dict, 'BaseFont')!r} {self.subtype}>"


def _num(value, default=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _base14_key(base_font: str) -> str:
    name = base_font.split("+")[-1].strip()
    lowered = name.lower()
    for key in ("courier", "helvetica", "times", "symbol", "zapfdingbats"):
        if key in lowered:
            if lowered.startswith("courier") and "bold" not in lowered and "italic" not in lowered:
                return "courier"
            if lowered.startswith("courier"):
                return "courier"
            if lowered.startswith("helvetica") or lowered.startswith("arial"):
                return "helvetica"
            if lowered.startswith("times") or lowered.startswith("serif"):
                return "times"
            if lowered.startswith("symbol"):
                return "symbol"
            if "zapf" in lowered:
                return "zapfdingbats"
    if lowered.startswith("arial"):
        return "helvetica"
    return ""


def parse_tounicode(payload: bytes) -> dict:
    """Parse the ``bfchar``/``bfrange`` sections of a ToUnicode CMap.

    Written as an explicit state machine over the CMap operators rather than a
    generic operand stack, because codespace ranges (``begincodespacerange``)
    also push byte strings and would otherwise be mistaken for mappings.

    Operands precede their closing operator, so each section is drained when
    ``endbfchar``/``endbfrange`` is reached.
    """
    mapping: dict[int, str] = {}
    stack: list = []
    mode = None
    for kind, value in tokenize_operators(payload):
        if kind == "obj":
            stack.append(value)
            if len(stack) > 4096:
                del stack[:len(stack) - 64]
            continue
        op = value
        if op == "begincodespacerange":
            mode = "codespace"
            stack = []
        elif op == "beginbfchar":
            mode = "bfchar"
            stack = []
        elif op == "beginbfrange":
            mode = "bfrange"
            stack = []
        elif op == "endcodespacerange":
            mode = None
            stack = []
        elif op == "endbfchar":
            for index in range(0, len(stack) - 1, 2):
                _apply_bfchar(mapping, stack[index], stack[index + 1])
            mode = None
            stack = []
        elif op == "endbfrange":
            index = 0
            while index + 2 < len(stack):
                _apply_bfrange(mapping, stack[index], stack[index + 1],
                               stack[index + 2])
                index += 3
            mode = None
            stack = []
        # Any other operator (including a stray 'def') is ignored.
    return mapping


def _apply_bfchar(mapping: dict, source, target) -> None:
    if isinstance(source, bytes) and source:
        mapping[int.from_bytes(source, "big")] = (
            _utf16be(target) if isinstance(target, bytes) else "")


def _apply_bfrange(mapping: dict, low, high, target) -> None:
    if not (isinstance(low, bytes) and isinstance(high, bytes) and low and high):
        return
    start = int.from_bytes(low, "big")
    end = int.from_bytes(high, "big")
    if end < start or end - start > 0x10FFFF:
        return
    if isinstance(target, bytes):
        base = _utf16be(target)
        # Destination may be multi-codepoint; increment its last codepoint.
        for offset in range(end - start + 1):
            mapping[start + offset] = _offset_text(base, offset)
    elif isinstance(target, list):
        for offset, item in enumerate(target):
            if isinstance(item, bytes):
                mapping[start + offset] = _utf16be(item)


def _offset_text(text: str, steps: int) -> str:
    """``abc`` + 2 -> ``abe`` (PDF bfrange increments the final code point)."""
    if not text or steps <= 0:
        return text
    prefix, last = text[:-1], ord(text[-1])
    if last + steps > 0x10FFFF:
        return text
    return prefix + chr(last + steps)


def _utf16be(data: bytes) -> str:
    try:
        if len(data) % 2:
            data = data[:-1]
        return data.decode("utf-16-be", "ignore")
    except (UnicodeDecodeError, LookupError):  # pragma: no cover - defensive
        return data.decode("latin-1", "ignore")


# Base-14 widths: generated from the standard AFM metrics. Only the Latin
# range plus common punctuation is needed for spacing accuracy.
_BASE14_WIDTHS = {
    "courier": {c: 600 for c in range(256)},
    "helvetica": None,
    "times": None,
    "symbol": None,
    "zapfdingbats": None,
}

# Helvetica/Arial and Times widths, stored explicitly since Python has no AFM
# data. Values are in 1/1000 units.
_HELVETICA = {
    32: 278, 33: 278, 34: 355, 35: 556, 36: 556, 37: 889, 38: 667, 39: 191,
    40: 333, 41: 333, 42: 389, 43: 584, 44: 278, 45: 333, 46: 278, 47: 278,
    48: 556, 49: 556, 50: 556, 51: 556, 52: 556, 53: 556, 54: 556, 55: 556,
    56: 556, 57: 556, 58: 278, 59: 278, 60: 584, 61: 584, 62: 584, 63: 556,
    64: 1015, 65: 667, 66: 667, 67: 722, 68: 722, 69: 667, 70: 611, 71: 778,
    72: 722, 73: 278, 74: 500, 75: 667, 76: 556, 77: 833, 78: 722, 79: 778,
    80: 667, 81: 778, 82: 722, 83: 667, 84: 611, 85: 722, 86: 667, 87: 944,
    88: 667, 89: 667, 90: 611, 91: 278, 92: 278, 93: 278, 94: 469, 95: 556,
    96: 333, 97: 556, 98: 556, 99: 500, 100: 556, 101: 556, 102: 278,
    103: 556, 104: 556, 105: 222, 106: 222, 107: 500, 108: 222, 109: 833,
    110: 556, 111: 556, 112: 556, 113: 556, 114: 333, 115: 500, 116: 278,
    117: 556, 118: 500, 119: 722, 120: 500, 121: 500, 122: 500, 123: 334,
    124: 260, 125: 334, 126: 584,
}

_BASE14_WIDTHS["helvetica"] = {
    **dict.fromkeys(range(32, 126), 556),
    **_HELVETICA,
    160: 556, 169: 737, 174: 737, 176: 400, 181: 333, 183: 278, 215: 584,
    247: 584,
}

_TIMES = dict.fromkeys(range(32, 126), 500)
_TIMES.update({
    32: 250, 33: 333, 34: 408, 35: 500, 36: 500, 37: 833, 38: 778, 39: 180,
    40: 333, 41: 333, 42: 500, 43: 564, 44: 250, 45: 333, 46: 250, 47: 278,
    48: 500, 49: 500, 50: 500, 51: 500, 52: 500, 53: 500, 54: 500, 55: 500,
    56: 500, 57: 500, 58: 278, 59: 278, 60: 564, 61: 564, 62: 564, 63: 444,
    64: 921, 65: 722, 66: 667, 67: 667, 68: 722, 69: 611, 70: 556, 71: 722,
    72: 722, 73: 333, 74: 389, 75: 722, 76: 611, 77: 889, 78: 722, 79: 722,
    80: 556, 81: 722, 82: 667, 83: 556, 84: 611, 85: 722, 86: 722, 87: 944,
    88: 722, 89: 611, 90: 722, 91: 333, 92: 278, 93: 333, 94: 469, 95: 500,
    96: 333, 97: 444, 98: 500, 99: 444, 100: 500, 101: 444, 102: 333, 103: 500,
    104: 500, 105: 278, 106: 278, 107: 500, 108: 278, 109: 778, 110: 500,
    111: 500, 112: 500, 113: 500, 114: 389, 115: 389, 116: 278, 117: 500,
    118: 500, 119: 722, 120: 500, 121: 500, 122: 444, 123: 480, 124: 200,
    125: 480, 126: 541, 160: 444, 169: 760, 174: 760, 176: 333, 181: 333,
    183: 333, 215: 564, 247: 564,
})
_BASE14_WIDTHS["times"] = _TIMES
_BASE14_WIDTHS["symbol"] = dict.fromkeys(range(32, 126), 549)
_BASE14_WIDTHS["zapfdingbats"] = dict.fromkeys(range(32, 126), 747)

__all__ = ["Font", "parse_tounicode", "STANDARD_ENCODING", "WIN_ANSI", "MAC_ROMAN"]