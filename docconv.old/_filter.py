import zlib

from ._obj import Stream


class FilterError(ValueError):
    """Raised when a stream's filter chain cannot be decoded."""


# -- individual filters --------------------------------------------------
def flate_decode(data: bytes) -> bytes:
    """Inflate, tolerating truncated tails and raw deflate headers."""
    if not data:
        return b""
    try:
        return zlib.decompress(data)
    except zlib.error:
        pass
    # Producers sometimes append junk after the deflate block, or truncate the
    # final byte. Try progressively: skip leading whitespace, then feed the
    # decompressor incrementally and keep whatever came out.
    stripped = data.lstrip(b"\r\n\t \x00")
    for candidate in (stripped, stripped[:-1] if len(stripped) > 1 else b""):
        if not candidate:
            continue
        try:
            return zlib.decompress(candidate)
        except zlib.error:
            pass
        try:
            return zlib.decompress(candidate, -15)
        except zlib.error:
            pass
    for wbits in (15, -15, 47):
        obj = zlib.decompressobj(wbits)
        try:
            out = obj.decompress(data)
            out += obj.flush()
        except zlib.error:
            try:
                out = obj.decompress(data.lstrip(b"\r\n\t \x00"))
                out += obj.flush()
            except zlib.error:
                continue
        if out:
            return out
    # Last resort: skip the leading garbage byte by byte.
    for skip in range(1, min(8, len(stripped))):
        try:
            return zlib.decompressobj().decompress(stripped[skip:])
        except zlib.error:
            continue
    raise FilterError("Gagal inflatable stream FlateDecode.")


def lzw_decode(data: bytes, early_change: int = 1) -> bytes:
    """LZW as used by PDF (variable code width 9..12, MSB first)."""
    out = bytearray()
    table = {i: bytes([i]) for i in range(256)}
    next_code = 258
    code_width = 9
    previous = None
    bitpos = 0
    total_bits = len(data) * 8
    while bitpos + code_width <= total_bits:
        byte_index = bitpos >> 3
        chunk = data[byte_index:byte_index + 3]
        if len(chunk) < 3:
            chunk = chunk + b"\x00" * (3 - len(chunk))
        window = (chunk[0] << 16) | (chunk[1] << 8) | chunk[2]
        shift = 24 - (bitpos & 7) - code_width
        code = (window >> shift) & ((1 << code_width) - 1)
        bitpos += code_width
        if code == 256:
            table = {i: bytes([i]) for i in range(256)}
            next_code = 258
            code_width = 9
            previous = None
            continue
        if code == 257:
            break
        if previous is None:
            if code in table:
                entry = table[code]
            else:
                break
        elif code in table:
            entry = table[code]
            table[next_code] = previous + entry[:1]
            next_code += 1
        else:
            entry = previous + previous[:1]
            table[next_code] = entry
            next_code += 1
        out += entry
        previous = entry
        limit = next_code + early_change
        if limit >= 512 and code_width == 9:
            code_width = 10
        elif limit >= 1024 and code_width == 10:
            code_width = 11
        elif limit >= 2048 and code_width == 11:
            code_width = 12
    return bytes(out)


def ascii85_decode(data: bytes) -> bytes:
    """Adobe ASCII85, tolerating ``<~`` prefix and ``~>`` terminator."""
    if data.startswith(b"<~"):
        data = data[2:]
    end = data.find(b"~>")
    if end >= 0:
        data = data[:end]
    out = bytearray()
    group: list[int] = []
    for byte in data:
        if byte in b" \t\r\n\x0c\x00":
            continue
        if byte == 0x7A and not group:  # 'z'
            out += b"\x00\x00\x00\x00"
            continue
        if not (0x21 <= byte <= 0x75):
            continue
        group.append(byte - 0x21)
        if len(group) == 5:
            value = 0
            for digit in group:
                value = value * 85 + digit
            # 85**5 exceeds 2**32, so a malformed producer can overflow here.
            out += (value & 0xFFFFFFFF).to_bytes(4, "big")
            group = []
    if group:
        count = len(group)
        group += [84] * (5 - count)
        value = 0
        for digit in group:
            value = value * 85 + digit
        out += value.to_bytes(4, "big")[:count - 1]
    return bytes(out)


def asciihex_decode(data: bytes) -> bytes:
    end = data.find(b">")
    if end >= 0:
        data = data[:end]
    digits = bytes(b for b in data if chr(b) in "0123456789abcdefABCDEF")
    if len(digits) % 2:
        digits += b"0"
    try:
        return bytes.fromhex(digits.decode("ascii"))
    except ValueError:  # pragma: no cover - defensive
        return b""


def runlength_decode(data: bytes) -> bytes:
    out = bytearray()
    pos = 0
    end = len(data)
    while pos < end:
        length = data[pos]
        pos += 1
        if length == 128:
            break
        if length < 128:
            out += data[pos:pos + length + 1]
            pos += length + 1
        else:
            if pos >= end:
                break
            out += bytes([data[pos]]) * (257 - length)
            pos += 1
    return bytes(out)


def apply_png_predictor(data: bytes, colors: int, bpc: int, columns: int) -> bytes:
    """Undo PNG row filters (predictor >= 10)."""
    bpp = max(1, (colors * bpc + 7) // 8)
    row_length = (columns * colors * bpc + 7) // 8
    out = bytearray()
    previous = bytearray(row_length)
    pos = 0
    end = len(data)
    while pos < end:
        filter_type = data[pos]
        pos += 1
        row = bytearray(data[pos:pos + row_length])
        if not row:
            break
        if len(row) < row_length:
            row += bytearray(row_length - len(row))
        pos += row_length
        if filter_type == 0:
            pass
        elif filter_type == 1:
            for i in range(bpp, row_length):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif filter_type == 2:
            for i in range(row_length):
                row[i] = (row[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(row_length):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(row_length):
                left = row[i - bpp] if i >= bpp else 0
                up = previous[i]
                upleft = previous[i - bpp] if i >= bpp else 0
                estimate = left + up - upleft
                dist_left = abs(estimate - left)
                dist_up = abs(estimate - up)
                dist_upleft = abs(estimate - upleft)
                if dist_left <= dist_up and dist_left <= dist_upleft:
                    predictor = left
                elif dist_up <= dist_upleft:
                    predictor = up
                else:
                    predictor = upleft
                row[i] = (row[i] + predictor) & 0xFF
        else:
            pass
        out += row
        previous = row
        if pos >= end:
            break
    return bytes(out)


def apply_tiff_predictor(data: bytes, colors: int, bpc: int, columns: int) -> bytes:
    if bpc != 8:
        # Sub-byte TIFF prediction is rare in PDFs; pass data through.
        return data
    row_length = columns * colors
    out = bytearray(data)
    for row_start in range(0, len(out) - row_length + 1, row_length):
        for i in range(colors, row_length):
            out[row_start + i] = (out[row_start + i] + out[row_start + i - colors]) & 0xFF
    return bytes(out)


_DECODERS = {
    "FlateDecode": flate_decode,
    "Fl": flate_decode,
    "LZWDecode": lzw_decode,
    "LZW": lzw_decode,
    "ASCII85Decode": ascii85_decode,
    "A85": ascii85_decode,
    "ASCIIHexDecode": asciihex_decode,
    "AHx": asciihex_decode,
    "RunLengthDecode": runlength_decode,
    "RL": runlength_decode,
}

IMAGE_FILTERS = {"DCTDecode", "JPXDecode", "JBIG2Decode", "CCITTFaxDecode", "DCT", "CCF"}


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def apply_filters(stream: Stream, doc=None) -> bytes:
    """Run a stream's ``/Filter`` chain and undo ``/DecodeParms`` predictors."""
    data = stream.rawdata
    dictionary = stream.dict

    def resolve(value):
        if doc is None:
            return value
        from ._obj import resolve as _resolve

        return _resolve(value, doc)

    filters = [str(resolve(f)) for f in _as_list(dictionary.get("Filter"))]
    if not filters:
        return data
    parms = [resolve(p) for p in _as_list(dictionary.get("DecodeParms", dictionary.get("DP")))]
    while len(parms) < len(filters):
        parms.append(None)
    for name, parm in zip(filters, parms):
        if name in IMAGE_FILTERS:
            # Image codecs are not re-encoded; hand back the payload untouched.
            return data
        decoder = _DECODERS.get(name)
        if decoder is None:
            raise FilterError(f"Filter tidak dikenal: {name}")
        data = decoder(data)
        parm = parm if isinstance(parm, dict) else {}
        predictor = int(resolve(parm.get("Predictor")) or 1)
        if predictor <= 1:
            continue
        colors = int(resolve(parm.get("Colors")) or 1)
        bpc = int(resolve(parm.get("BitsPerComponent")) or 8)
        columns = int(resolve(parm.get("Columns")) or 1)
        if predictor == 2:
            data = apply_tiff_predictor(data, colors, bpc, columns)
        else:
            data = apply_png_predictor(data, colors, bpc, columns)
    return data


__all__ = [
    "FilterError",
    "flate_decode",
    "lzw_decode",
    "ascii85_decode",
    "asciihex_decode",
    "runlength_decode",
    "apply_filters",
    "apply_png_predictor",
]