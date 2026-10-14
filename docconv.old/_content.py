import math

from ._obj import tokenize_operators
from ._xref import PdfDocument


class TextRun:
    """A positioned piece of text.

    ``text`` is already Unicode-decoded; ``x``/``y`` is the baseline origin in
    user space; ``size`` is the effective font size after the text matrix; and
    ``width`` is the advance width in user space units.
    """

    __slots__ = ("text", "x", "y", "width", "size", "font", "height", "upright")

    def __init__(self, text, x, y, width, size, font=None, upright=True):
        self.text = text
        self.x = x
        self.y = y
        self.width = width
        self.size = size
        self.font = font
        self.height = abs(size) if size else 0.0
        self.upright = upright

    @property
    def top(self):
        return self.y + (self.size * 0.75 if self.upright else 0)

    @property
    def bottom(self):
        return self.y - (self.size * 0.25 if self.upright else 0)

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<TextRun {self.text!r} @({self.x:.1f},{self.y:.1f})>"


class Char:
    """Positioned glyph, used for line/column clustering."""

    __slots__ = ("text", "x0", "x1", "y0", "y1", "size")

    def __init__(self, text, x0, x1, y0, y1, size):
        self.text = text
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.y1 = y1
        self.size = size

    @property
    def width(self):
        return self.x1 - self.x0


class LineSegment:
    """A horizontal-ish run of glyphs, the unit table detection consumes."""

    __slots__ = ("chars", "x0", "x1", "top", "bottom", "size")

    def __init__(self, chars):
        self.chars = chars
        self.x0 = min(c.x0 for c in chars)
        self.x1 = max(c.x1 for c in chars)
        self.top = max(c.y1 for c in chars)
        self.bottom = min(c.y0 for c in chars)
        self.size = max(c.size for c in chars) if chars else 0.0

    @property
    def text(self):
        return "".join(c.text for c in self.chars)

    @property
    def center_y(self):
        return (self.top + self.bottom) / 2


class Rect:
    """A filled rectangle (background), used as a table-cell hint."""

    __slots__ = ("x0", "y0", "x1", "y1")

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.x1 = min(x0, x1), max(x0, x1)
        self.y0, self.y1 = min(y0, y1), max(y0, y1)

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0


class GraphicsState:
    """Subset of the graphics state that affects text placement."""

    __slots__ = ("ctm", "font", "font_size", "char_spacing", "word_spacing",
                 "horizontal_scale", "leading", "rise", "render_mode")

    def __init__(self, ctm):
        self.ctm = ctm
        self.font = None
        self.font_size = 0.0
        self.char_spacing = 0.0
        self.word_spacing = 0.0
        self.horizontal_scale = 1.0
        self.leading = 0.0
        self.rise = 0.0
        self.render_mode = 0

    def copy(self):
        clone = GraphicsState(self.ctm)
        clone.font = self.font
        clone.font_size = self.font_size
        clone.char_spacing = self.char_spacing
        clone.word_spacing = self.word_spacing
        clone.horizontal_scale = self.horizontal_scale
        clone.leading = self.leading
        clone.rise = self.rise
        clone.render_mode = self.render_mode
        return clone


IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def multiply(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + b * c2,
        a * b2 + b * d2,
        c * a2 + d * c2,
        c * b2 + d * d2,
        e * a2 + f * c2 + e2,
        e * b2 + f * d2 + f2,
    )


def apply_matrix(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


class ContentParser:
    """Executes a content stream against a page's resources."""

    def __init__(self, doc: PdfDocument, resources: dict):
        self.doc = doc
        self.resources = resources if isinstance(resources, dict) else {}
        self.runs: list[TextRun] = []
        self.chars: list[Char] = []
        self.rects: list[Rect] = []
        self.lines: list[tuple] = []  # (x0, y0, x1, y1) stroked paths
        self._font_cache: dict = {}
        self._font = None

    def parse(self, data: bytes) -> None:
        if not data:
            return
        state = GraphicsState(IDENTITY)
        stack: list[GraphicsState] = []
        text_matrix = IDENTITY
        line_matrix = IDENTITY
        in_text = False
        font = None
        font_size = 0.0
        char_spacing = 0.0
        word_spacing = 0.0
        hscale = 1.0
        leading = 0.0
        rise = 0.0
        render_mode = 0
        operands: list = []
        path: list[tuple[float, float]] = []
        pending_rects: list[Rect] = []

        for kind, value in tokenize_operators(data):
            if kind == "obj":
                if len(operands) < 64:
                    operands.append(value)
                continue
            op = value

            # --- graphics state ---
            if op == "q":
                stack.append(state.copy())
            elif op == "Q":
                if stack:
                    saved = stack.pop()
                    text_matrix = saved.ctm  # keep text matrix tied to CTM restore
                    state = saved
            elif op == "cm" and len(operands) >= 6:
                extra = tuple(float(v) for v in _numtail(operands, 6))
                state.ctm = multiply(extra, state.ctm)
            elif op == "gs":
                pass

            # --- text object ---
            elif op == "BT":
                in_text = True
                text_matrix = IDENTITY
                line_matrix = IDENTITY
            elif op == "ET":
                in_text = False
            elif op == "Tf" and len(operands) >= 2:
                font_name = operands[-2]
                size = operands[-1]
                font_size = _to_float(size)
                font = self._resolve_font(font_name)
            elif op == "Td" and len(operands) >= 2:
                tx, ty = _to_float(operands[-2]), _to_float(operands[-1])
                line_matrix = multiply((1, 0, 0, 1, tx, ty), line_matrix)
                text_matrix = line_matrix
            elif op == "TD" and len(operands) >= 2:
                tx, ty = _to_float(operands[-2]), _to_float(operands[-1])
                leading = -ty
                line_matrix = multiply((1, 0, 0, 1, tx, ty), line_matrix)
                text_matrix = line_matrix
            elif op == "Tm" and len(operands) >= 6:
                line_matrix = tuple(_to_float(v) for v in _numtail(operands, 6))
                text_matrix = line_matrix
            elif op == "T*":
                text_matrix = line_matrix = multiply((1, 0, 0, 1, 0, -leading), line_matrix)
            elif op == "TL" and operands:
                leading = _to_float(operands[-1])
            elif op == "Tc" and operands:
                char_spacing = _to_float(operands[-1])
            elif op == "Tw" and operands:
                word_spacing = _to_float(operands[-1])
            elif op == "Tz" and operands:
                hscale = _to_float(operands[-1]) / 100.0
            elif op == "Ts" and operands:
                rise = _to_float(operands[-1])
            elif op == "Tr" and operands:
                render_mode = int(_to_float(operands[-1]))

            # --- text showing ---
            elif op == "Tj" and operands:
                text_matrix = self._show(
                    operands[-1], font, font_size, char_spacing, word_spacing,
                    hscale, rise, render_mode, text_matrix, state.ctm)
            elif op == "TJ" and operands:
                array = operands[-1]
                if isinstance(array, list):
                    for item in array:
                        if isinstance(item, (int, float)) and not isinstance(item, bool):
                            shift = -item / 1000.0 * font_size * hscale
                            text_matrix = multiply((1, 0, 0, 1, shift, 0), text_matrix)
                        elif isinstance(item, bytes):
                            text_matrix = self._show(
                                item, font, font_size, char_spacing, word_spacing,
                                hscale, rise, render_mode, text_matrix, state.ctm)
            elif op == "'" and operands:
                text_matrix = line_matrix = multiply((1, 0, 0, 1, 0, -leading), line_matrix)
                text_matrix = self._show(
                    operands[-1], font, font_size, char_spacing, word_spacing,
                    hscale, rise, render_mode, text_matrix, state.ctm)
            elif op == '"' and len(operands) >= 3:
                word_spacing = _to_float(operands[-3])
                char_spacing = _to_float(operands[-2])
                text_matrix = line_matrix = multiply((1, 0, 0, 1, 0, -leading), line_matrix)
                text_matrix = self._show(
                    operands[-1], font, font_size, char_spacing, word_spacing,
                    hscale, rise, render_mode, text_matrix, state.ctm)

            # --- path construction (for ruling-line detection) ---
            elif op == "m" and len(operands) >= 2:
                path = [(_to_float(operands[-2]), _to_float(operands[-1]))]
            elif op == "l" and len(operands) >= 2:
                path.append((_to_float(operands[-2]), _to_float(operands[-1])))
            elif op in ("c", "v", "y") and len(operands) >= 2:
                path.append((_to_float(operands[-2]), _to_float(operands[-1])))
            elif op == "re" and len(operands) >= 4:
                x, y, w, h = (_to_float(v) for v in _numtail(operands, 4))
                pending_rects.append(Rect(x, y, x + w, y + h))
                path = [(x, y), (x + w, y + h)]
            elif op in _PATH_PAINT_OPS:
                if op in ("b", "b*") and path:
                    path.append(path[0])
                if op != "n":
                    for rect in pending_rects:
                        corners = [apply_matrix(state.ctm, rx, ry)
                                   for rx, ry in _rect_corners(rect)]
                        self.rects.append(_bounding_rect(corners))
                    if op in _STROKE_PAINT_OPS:
                        self._emit_path(state.ctm, path)
                pending_rects = []
                path = []
            elif op in _STROKE_OPS:
                if op == "s" and path:
                    path.append(path[0])
                self._emit_path(state.ctm, path)
                path = []
            elif op == "n":
                path = []
                pending_rects = []
            elif op in ("W", "W*"):
                pass

            if op not in _INCOMPLETE_OPERATOR:
                operands = []

    def _emit_path(self, ctm, path) -> None:
        """Record a stroked path as potential table ruling lines."""
        if len(path) < 2:
            return
        points = [apply_matrix(ctm, x, y) for x, y in path]
        self.lines.extend(_polyline_segments(points))

    def _resolve_font(self, name):
        from ._font import Font

        if name is None:
            return None
        fonts = self.doc.resolve(self.resources.get("Font"))
        key = str(name)
        if key in self._font_cache:
            return self._font_cache[key]
        dictionary = None
        if isinstance(fonts, dict):
            entry = fonts.get(key)
            if entry is None and key.startswith("/"):
                entry = fonts.get(key[1:])
            resolved = self.doc.resolve(entry)
            if isinstance(resolved, dict):
                dictionary = resolved
        if dictionary is None:
            # Some producers reference fonts only by a name that is not in
            # /Font; fall back to the raw key so the run still gets recorded.
            self._font_cache[key] = None
            return None
        font = Font(dictionary, self.doc)
        self._font_cache[key] = font
        return font

    def _show(self, raw, font, font_size, char_spacing, word_spacing, hscale,
              rise, render_mode, text_matrix, ctm):
        """Emit glyphs for one show operator; returns the advanced matrix."""
        if not isinstance(raw, bytes):
            return text_matrix
        matrix = multiply((1, 0, 0, 1, 0, rise), multiply(text_matrix, ctm))
        scale_x = math.hypot(matrix[0], matrix[1])
        scale_y = math.hypot(matrix[2], matrix[3])
        effective_size = font_size * (scale_y if scale_y > 1e-6 else scale_x or 1.0)
        if font is not None:
            pieces = font.decode(raw)
        else:
            pieces = [(raw.decode("latin-1"), len(raw))]
        if not pieces:
            return text_matrix
        buffer = []
        start_x = None
        buffer_start_matrix = matrix
        advance = 0.0
        upright = abs(scale_y) >= abs(scale_x) or scale_y >= 1e-6

        for piece in pieces:
            code, value = piece[0], piece[1]
            text = code if isinstance(code, str) else str(code)
            if not text:
                continue
            if start_x is None:
                start_x = apply_matrix(matrix, 0, 0)
                buffer_start_matrix = matrix
                advance = 0.0
            buffer.append(text)
            glyph_width = font.char_width(value) if font is not None else 0.5
            w0 = glyph_width * font_size + char_spacing
            if code in (" ", "\u00a0") or value == 32:
                w0 += word_spacing
            step = (w0 / 1000.0 * hscale) if font is not None else (w0 * hscale)
            advance += step
            matrix = multiply((1, 0, 0, 1, step, 0), matrix)

        if not buffer:
            return text_matrix

        origin = start_x
        end_point = apply_matrix(buffer_start_matrix, advance, 0)
        run_width = math.hypot(end_point[0] - origin[0], end_point[1] - origin[1])
        if render_mode in (3, 7):  # invisible text: OCR overlay, skip
            return matrix
        text = "".join(buffer)
        self.runs.append(TextRun(text, origin[0], origin[1], run_width,
                                 effective_size, font, upright))
        # Per-character boxes let the layout stage build columns precisely.
        cursor = 0.0
        total = sum(len(t) for t in buffer) or 1
        per_char = advance / total
        for token in buffer:
            x0 = apply_matrix(buffer_start_matrix, cursor, 0)[0]
            cursor += per_char * len(token)
            x1 = apply_matrix(buffer_start_matrix, cursor, 0)[0]
            self.chars.append(Char(
                token,
                min(x0, x1), max(x0, x1),
                origin[1] - effective_size * 0.25,
                origin[1] + effective_size * 0.75,
                effective_size,
            ))
        return matrix


_STROKE_OPS = {"S", "s"}
_PATH_PAINT_OPS = {"f", "F", "f*", "B", "B*", "b", "b*", "n"}
_STROKE_PAINT_OPS = {"B", "B*", "b", "b*"}
# BDC/EMC wrap a marked-content section: keep accumulating operands.
_INCOMPLETE_OPERATOR = {"BDC"}


def _numtail(operands, count):
    values = operands[-count:]
    if len(values) < count:
        return [0] * (count - len(values)) + list(values)
    return list(values)


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rect_corners(rect: Rect):
    return [(rect.x0, rect.y0), (rect.x1, rect.y0), (rect.x1, rect.y1), (rect.x0, rect.y1)]


def _bounding_rect(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return Rect(min(xs), min(ys), max(xs), max(ys))


def _polyline_segments(points):
    segments = []
    for i in range(len(points) - 1):
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        if abs(x0 - x1) < 0.01 and abs(y0 - y1) < 0.01:
            continue
        segments.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    return segments


def parse_page(doc: PdfDocument, page) -> ContentParser:
    """Run the interpreter over one page and return the populated parser."""
    parser = ContentParser(doc, page.resources)
    parser.parse(page.content_bytes())
    return parser


__all__ = ["ContentParser", "TextRun", "Char", "LineSegment", "Rect",
           "parse_page", "IDENTITY", "multiply", "apply_matrix"]
