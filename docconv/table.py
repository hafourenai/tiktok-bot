"""Table detection heuristics (stage P8).

Two strategies, in order of confidence:

1. **Ruled tables** - the page draws grid lines (``re``/``m``/``l`` + stroke or
   fill). Intersect horizontal and vertical rules into a grid, then assign glyph
   runs to cells.
2. **Unruled tables** - no usable rules, so look for at least three adjacent
   lines that share two or more column boundaries.

Anything ambiguous is left to the text path: a wrong table is worse than none.
"""

from ._content import LineSegment

MIN_TABLE_ROWS = 2
MIN_TABLE_COLUMNS = 2
# Boundary clustering tolerance, relative to the median font size.
BOUNDARY_TOLERANCE = 1.6
# Horizontal alignment agreement needed to call a column consistent.
ALIGN_TOLERANCE = 2.0


def detect_tables(lines, rulings=(), rects=(), page_width=0.0) -> list:
    """Return a list of tables, each a list of rows of cell strings."""
    if not lines:
        return []
    tables = []
    used = [False] * len(lines)

    for table in _ruled_tables(lines, rulings, rects):
        if table:
            tables.append(table)

    # Unruled detection over lines not already claimed by a ruled table.
    remaining = [index for index in range(len(lines)) if not used[index]]
    for group in _unruled_groups(lines, remaining):
        table = _group_to_table(lines, group)
        if table:
            for index in group:
                used[index] = True
            tables.append(table)

    tables.sort(key=lambda t: -_table_score(t))
    return tables


def _table_score(table) -> int:
    if not table:
        return 0
    return sum(len(row) for row in table) * 10 + len(table)


# -- ruled tables ---------------------------------------------------------
def _ruled_tables(lines, rulings, rects):
    horizontals = [r for r in rulings if _is_horizontal(r)]
    verticals = [r for r in rulings if _is_vertical(r)]
    if not horizontals and rects:
        # Filled cell backgrounds act as rulings.
        for rect in rects:
            if rect.height <= 2.5 and rect.width > 8:
                horizontals.append((rect.x0, rect.y0, rect.x1, rect.y1))
            elif rect.width <= 2.5 and rect.height > 8:
                verticals.append((rect.x0, rect.y0, rect.x1, rect.y1))
    horizontals = _dedupe(horizontals)
    verticals = _dedupe(verticals)
    if len(horizontals) < 3 or len(verticals) < 2:
        return []

    h_positions = sorted((y0 + y1) / 2 for _, y0, _, y1 in horizontals)
    v_positions = sorted((x0 + x1) / 2 for x0, _, x1, _ in verticals)
    h_positions = _cluster_positions(h_positions)
    v_positions = _cluster_positions(v_positions)
    if len(h_positions) < 3 or len(v_positions) < 2:
        return []

    tables = []
    # A grid is a maximal run of consecutive rules; split on large gaps so two
    # separate tables on one page do not merge.
    for h_group in _split_runs(h_positions, gap_ratio=4.0):
        if len(h_group) < 3:
            continue
        for v_group in _split_runs(v_positions, gap_ratio=6.0):
            if len(v_group) < 2:
                continue
            table = _grid_to_table(lines, h_group, v_group)
            if table:
                tables.append(table)
    return tables


def _grid_to_table(lines, h_positions, v_positions):
    rows = []
    columns = len(v_positions) - 1
    if columns < 1:
        return []
    # h_positions ascend with y, i.e. bottom-up; emit rows top-down.
    for top, bottom in reversed(list(zip(h_positions, h_positions[1:]))):
        if bottom - top <= 0.5:
            continue
        row_lines = [seg for seg in lines if top < seg.center_y < bottom]
        if not row_lines:
            continue
        cells = [""] * columns
        for segment in row_lines:
            # A text line can span several cells, so split it at the vertical
            # rules instead of assigning the whole line to one column.
            for chunk in _split_segment_at(segment, v_positions):
                slot = _column_for(chunk, v_positions)
                if slot is None:
                    continue
                text = chunk.text.strip()
                if not text:
                    continue
                cells[slot] = f"{cells[slot]} {text}".strip() if cells[slot] else text
        if any(cells):
            rows.append(cells)
    if len(rows) < MIN_TABLE_ROWS:
        return []
    _trim_empty_edges(rows)
    if len(rows) < MIN_TABLE_ROWS:
        return []
    return rows


def _split_segment_at(segment, v_positions):
    """Cut a line segment into the pieces delimited by vertical rules."""
    cuts = [segment.x0]
    for boundary in v_positions:
        if segment.x0 + 0.5 < boundary < segment.x1 - 0.5:
            cuts.append(boundary)
    cuts.append(segment.x1)
    cuts.sort()
    out = []
    for left, right in zip(cuts, cuts[1:]):
        chars = sorted((c for c in segment.chars
                        if left - 0.5 <= c.x0 and c.x1 <= right + 0.5),
                       key=lambda c: c.x0)
        if chars:
            out.append(LineSegment(chars))
    return out


def _column_for(segment, v_positions) -> int | None:
    """Index of the column whose band contains the segment's centre."""
    centre = (segment.x0 + segment.x1) / 2
    for index, (left, right) in enumerate(zip(v_positions, v_positions[1:])):
        if left - 1.0 <= centre <= right + 1.0:
            return index
    if centre < v_positions[0]:
        return 0
    return len(v_positions) - 2


# -- unruled tables -------------------------------------------------------
# Without ruling lines the only reliable signal is *inter-word gaps*: in a real
# table the gaps between columns recur at nearly the same x on several rows.
# Prose paragraphs also contain gaps, but they drift with the line length, so
# requiring repeated gap centres is what separates the two cases.
MIN_ROWS_FOR_UNRULED = 3
# A gap must be at least this wide (relative to font size) to count as a
# column separator rather than ordinary word spacing.
MIN_COLUMN_GAP_RATIO = 0.9
# Gap centres must agree within this tolerance (relative to font size).
GAP_AGREEMENT_RATIO = 0.5
# Fraction of the group's rows that must share a boundary.
MIN_BOUNDARY_SHARE = 0.8


def _word_gaps(segment):
    """Wide internal gaps in a line, as (centre, width) pairs.

    Runs of whitespace-only glyphs (including the synthetic spaces the layout
    stage inserts for ordinary word spacing) are skipped, so what remains is a
    gap between two real words.
    """
    tokens = [c for c in segment.chars if c.text.strip()]
    gaps = []
    for left, right in zip(tokens, tokens[1:]):
        gap = right.x0 - left.x1
        if gap >= MIN_COLUMN_GAP_RATIO * max(left.size, 1.0):
            gaps.append((left.x1 + gap / 2.0, gap))
    return gaps


def _unruled_groups(lines, indices) -> list:
    """Maximal runs of vertically adjacent lines that agree on >=1 boundary."""
    if len(indices) < MIN_ROWS_FOR_UNRULED:
        return []
    ordered = sorted(indices, key=lambda i: (-lines[i].center_y, lines[i].x0))
    rows: list[list[int]] = [[ordered[0]]]
    for index in ordered[1:]:
        if _is_vertical_neighbour(lines[index], _band_centre(lines, rows[-1])):
            rows[-1].append(index)
        else:
            rows.append([index])
    groups = []
    for group in _expand_groups(rows):
        if len(group) >= MIN_ROWS_FOR_UNRULED and _columns_align(lines, group):
            groups.append(group)
    return groups


def _band_centre(lines, indices) -> float:
    return sum(lines[i].center_y for i in indices) / len(indices)


def _expand_groups(rows) -> list:
    """Slide a window over row groups so partial tables are not lost."""
    out = []
    size = MIN_ROWS_FOR_UNRULED
    start = 0
    while start < len(rows):
        for end in range(start + size - 1, len(rows) + 1):
            flat = [index for row in rows[start:end] for index in row]
            out.append(flat)
        start += 1
    # Prefer the longest groups; dedupe on membership.
    out.sort(key=len, reverse=True)
    chosen = []
    for group in out:
        if any(set(group) == set(kept) for kept in chosen):
            continue
        chosen.append(group)
    return chosen


def _is_vertical_neighbour(lower, upper_centre) -> bool:
    """True if a row sits just below the previous row's band."""
    return -0.4 * max(lower.size, 1.0) <= upper_centre - lower.center_y <= \
        2.4 * max(lower.size, 1.0)


def _columns_align(lines, indices) -> bool:
    """True if the rows agree on at least one column boundary position.

    Agreement is measured on gap centres, not on segment edges: text width
    varies per cell, so left/right edges of prose drift while the gap between
    columns stays put.
    """
    if len(indices) < MIN_ROWS_FOR_UNRULED:
        return False
    segments = [lines[i] for i in indices]
    sizes = sorted(s.size for s in segments if s.size > 0)
    median = sizes[len(sizes) // 2] if sizes else 10.0
    tolerance = max(2.0, GAP_AGREEMENT_RATIO * median)
    needed = max(2, int(round(MIN_BOUNDARY_SHARE * len(segments))))

    gap_lists = [_word_gaps(segment) for segment in segments]
    # Collect every gap centre, then keep the ones enough rows agree on.
    all_centres = [centre for gaps in gap_lists for centre, _ in gaps]
    for centre in all_centres:
        agreeing = 0
        for gaps in gap_lists:
            if any(abs(other - centre) <= tolerance for other, _ in gaps):
                agreeing += 1
        if agreeing >= needed:
            return True
    return False


def _group_to_table(lines, indices) -> list:
    """Build a grid from the gap boundaries the rows agree on."""
    segments = [lines[i] for i in indices]
    sizes = sorted(s.size for s in segments if s.size > 0)
    median = sizes[len(sizes) // 2] if sizes else 10.0
    tolerance = max(2.0, GAP_AGREEMENT_RATIO * median)
    needed = max(2, int(round(MIN_BOUNDARY_SHARE * len(segments))))

    gap_lists = [_word_gaps(segment) for segment in segments]
    votes: dict[int, list[float]] = {}
    for gaps in gap_lists:
        seen_local = set()
        for centre, _ in gaps:
            if any(abs(centre - key) <= tolerance for key in seen_local):
                continue
            seen_local.add(centre)
            for key in list(votes):
                if abs(centre - key) <= tolerance:
                    votes[key].append(centre)
                    break
            else:
                votes[centre] = [centre]

    boundaries_set = [key for key, hits in votes.items() if len(hits) >= needed]
    if len(boundaries_set) < MIN_TABLE_COLUMNS:
        return []
    left = min(s.x0 for s in segments)
    right = max(s.x1 for s in segments)
    boundaries = [left] + sorted(boundaries_set) + [right]

    rows = []
    for index in sorted(indices, key=lambda i: (-lines[i].center_y, lines[i].x0)):
        cells = [""] * (len(boundaries) - 1)
        for line_index in indices:
            segment = lines[line_index]
            if abs(segment.center_y - lines[index].center_y) > 1e-6:
                continue
            for chunk in _split_segment_at(segment, boundaries) or [segment]:
                slot = _column_for(chunk, boundaries)
                if slot is None or slot >= len(cells):
                    continue
                text = chunk.text.strip()
                if not text:
                    continue
                cells[slot] = f"{cells[slot]} {text}".strip() if cells[slot] else text
        if any(cells):
            rows.append(cells)
    if len(rows) < MIN_ROWS_FOR_UNRULED:
        return []
    _trim_empty_edges(rows)
    return rows if len(rows) >= MIN_ROWS_FOR_UNRULED else []



# -- helpers --------------------------------------------------------------
def _is_horizontal(ruling) -> bool:
    x0, y0, x1, y1 = ruling
    return abs(y1 - y0) <= 2.0 and abs(x1 - x0) >= 8.0


def _is_vertical(ruling) -> bool:
    x0, y0, x1, y1 = ruling
    return abs(x1 - x0) <= 2.0 and abs(y1 - y0) >= 8.0


def _dedupe(rulings):
    out = []
    for ruling in rulings:
        if not any(_close(ruling, kept) for kept in out):
            out.append(ruling)
    return out


def _close(a, b) -> bool:
    return all(abs(x - y) <= 1.5 for x, y in zip(a, b))


def _cluster_positions(values):
    if not values:
        return []
    values = sorted(values)
    clusters = [[values[0]]]
    for value in values[1:]:
        if value - clusters[-1][-1] <= 2.0:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return [sum(group) / len(group) for group in clusters]


def _split_runs(positions, gap_ratio=4.0):
    if not positions:
        return []
    if len(positions) == 1:
        return [positions]
    spans = [b - a for a, b in zip(positions, positions[1:])]
    ordered = sorted(spans)
    median = ordered[len(ordered) // 2] or 1.0
    limit = max(median * gap_ratio, median + 1.0)
    runs = [[positions[0]]]
    for index, value in enumerate(positions[1:]):
        if spans[index] > limit:
            runs.append([value])
        else:
            runs[-1].append(value)
    return runs


def _trim_empty_edges(rows):
    while rows and not any(cell.strip() for cell in rows[-1]):
        rows.pop()
    while rows and not any(cell.strip() for cell in rows[0]):
        rows.pop(0)
    if not rows:
        return
    keep = 0
    for column in range(len(rows[0])):
        if any(row[column].strip() for row in rows if column < len(row)):
            keep = max(keep, column + 1)
    if keep:
        for row in rows:
            del row[keep:]


__all__ = ["detect_tables"]