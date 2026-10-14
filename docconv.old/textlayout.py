"""Text layout analysis for PDF content.

Reconstructs words from horizontal gaps and lines from baseline clustering.
"""

from ._content import Char, LineSegment

# A gap is a word separator when it exceeds this multiple of the font size.
WORD_GAP_RATIO = 0.22
# Baselines within this fraction of the line height belong to the same line.
LINE_TOLERANCE = 0.55


def _is_space(ch: Char) -> bool:
    return ch.text.strip() == ""


def build_lines(chars: list, page_width: float = 0.0) -> list[LineSegment]:
    """Group glyphs into lines, ordered top-to-bottom then left-to-right."""
    if not chars:
        return []
    sized = [c for c in chars if c.text]
    if not sized:
        return []

    # Sort by descending baseline so index 0 is the top of the page.
    sized.sort(key=lambda c: (-c.y0, c.x0))

    buckets: list[list[Char]] = []
    current: list[Char] = []
    reference = None
    for ch in sized:
        if reference is None:
            reference = _baseline(ch)
            current = [ch]
            continue
        tolerance = max(1.0, LINE_TOLERANCE * max(ch.size, 1.0))
        if abs(_baseline(ch) - reference) <= tolerance:
            current.append(ch)
        else:
            buckets.append(current)
            current = [ch]
            reference = _baseline(ch)
    if current:
        buckets.append(current)

    lines = []
    for bucket in buckets:
        bucket.sort(key=lambda c: (c.x0, c.x1))
        lines.append(LineSegment(_merge_within_words(bucket)))
    # Stable vertical order: top of page first.
    lines.sort(key=lambda seg: (-seg.top, seg.x0))
    return lines


def _baseline(ch: Char) -> float:
    return (ch.y0 + ch.y1) / 2


def _merge_within_words(chars: list) -> list:
    """Insert real spaces where the geometry says a space was drawn."""
    out: list[Char] = []
    for index, ch in enumerate(chars):
        if index:
            previous = out[-1]
            gap = ch.x0 - previous.x1
            reference = _space_width(chars, index)
            if not _is_space(previous) and not _is_space(ch):
                if reference > 0 and gap > max(1.0, WORD_GAP_RATIO * reference):
                    out.append(Char(" ", previous.x1, previous.x1 + reference,
                                    previous.y0, previous.y1, previous.size))
            elif _is_space(previous) and not _is_space(ch):
                pass
        if _is_space(ch) and (not out or _is_space(out[-1])):
            # Drop leading/duplicate spaces; keep the original geometry.
            previous = out[-1] if out else None
            if previous is None or ch.x0 - previous.x1 > max(1.0, ch.size * WORD_GAP_RATIO):
                out.append(ch)
            continue
        out.append(ch)
    while out and _is_space(out[-1]):
        out.pop()
    return out


def _space_width(chars: list, index: int) -> float:
    """Estimate the advance width of a space in this run."""
    for probe in (index - 1, index):
        for candidate in chars:
            if candidate.text == " ":
                return max(1.0, candidate.width)
    size = max((c.size for c in chars), default=10.0)
    return size * 0.25


def line_text(segment: LineSegment) -> str:
    return segment.text


def lines_to_text(lines: list[LineSegment], separator: str = "\n") -> str:
    out = []
    for segment in lines:
        text = segment.text.rstrip()
        if text:
            out.append(text)
    return separator.join(out)


def reading_order_text(lines: list[LineSegment]) -> str:
    """Text in reading order, with blank lines where the vertical gap is large.

    Keeping one blank line between paragraphs makes the DOCX/XLSX output
    readable, which is what users actually see.
    """
    out: list[str] = []
    previous_bottom = None
    for segment in lines:
        text = segment.text.rstrip()
        if not text:
            continue
        if previous_bottom is not None:
            gap = previous_bottom - segment.top
            if gap > segment.size * 0.9:
                out.append("")
        out.append(text)
        previous_bottom = segment.bottom
    return "\n".join(out)


__all__ = ["build_lines", "lines_to_text", "reading_order_text", "line_text"]