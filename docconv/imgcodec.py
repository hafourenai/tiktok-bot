"""Image handling for document conversion.

Read/write PNG/JPEG, optimize images, extract metadata.
Uses only stdlib (struct, zlib) to avoid external image dependencies.
"""

import struct
import zlib
import io
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

_PNG_DIMENSIONS = {
    # IHDR is always the first chunk; its layout never varies.
    "width": 16,
    "height": 20,
}


class ImageError(ValueError):
    """Raised for unsupported or malformed image data."""


def read_dimensions(data: bytes) -> tuple:
    """Return ``(width, height)`` for PNG or JPEG bytes."""
    if data.startswith(PNG_SIGNATURE):
        if len(data) < 24:
            raise ImageError("Berkas PNG terpotong.")
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)

    if data.startswith(b"\xff\xd8"):
        return _jpeg_dimensions(data)

    raise ImageError("Format gambar tidak didukung; yang bisa dibaca: PNG dan JPEG.")


def read_dimensions_file(path) -> tuple:
    with open(path, "rb") as handle:
        head = handle.read(65536)
    return read_dimensions(head)


def _jpeg_dimensions(data: bytes) -> tuple:
    """Walk JPEG markers to the SOFn frame header."""
    pos = 2
    end = len(data)
    while pos + 3 < end:
        if data[pos] != 0xFF:
            pos += 1
            continue
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        if marker == 0xD9 or marker == 0xDA:  # end of image / start of scan
            break
        if pos + 4 > end:
            break
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        # SOF0..SOF15, excluding the DHT/JPG/DAC markers in that range.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if pos + 9 <= end:
                height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
                return int(width), int(height)
        pos += 2 + length
    raise ImageError("Header JPEG tidak lengkap.")


def _chunk(tag: bytes, payload: bytes) -> bytes:
    body = tag + payload
    return (struct.pack(">I", len(payload)) + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def write_png(width: int, height: int, pixels, greyscale: bool = False) -> bytes:
    """Build a PNG from raw samples.

    ``pixels`` is a flat bytes-like of ``width * height`` samples (8-bit grey)
    or ``width * height * 3`` (8-bit RGB). Filtering is skipped: the encoder
    emits stored (filter type 0) rows, which every decoder accepts.
    """
    width, height = int(width), int(height)
    if width <= 0 or height <= 0:
        raise ImageError("Dimensi gambar tidak valid.")
    channels = 1 if greyscale else 3
    expected = width * height * channels
    pixels = bytes(pixels)
    if len(pixels) < expected:
        raise ImageError(
            f"Data piksel kurang: butuh {expected} byte, diterima {len(pixels)}."
        )
    color_type = 0 if greyscale else 2
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    stride = width * channels
    raw = bytearray()
    for row in range(height):
        raw.append(0)  # filter type: None
        raw += pixels[row * stride:(row + 1) * stride]
    return (PNG_SIGNATURE
            + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + _chunk(b"IEND", b""))


def save_png(path, width: int, height: int, pixels, greyscale: bool = False) -> str:
    with open(path, "wb") as handle:
        handle.write(write_png(width, height, pixels, greyscale))
    return str(path)


def image_to_pdf(image_path: str, output_path: str, dpi: float = 100.0) -> str:
    """Wrap a PNG/JPEG file in a single-page PDF.

    JPEG data is embedded verbatim via ``/DCTDecode`` (no re-encoding), and PNG
    is passed through as ``/FlateDecode`` when it is a non-interlaced 8-bit
    image, which is what ``pdftoppm`` and screen captures produce.
    """
    from .pdfwrite import PdfWriter, PlacedImage

    with open(image_path, "rb") as handle:
        data = handle.read()
    width_px, height_px = read_dimensions(data)

    # 1 inch = 72 user units, so px / dpi * 72 gives the page size.
    scale = 72.0 / max(dpi, 1.0)
    page_width = max(1.0, width_px * scale)
    page_height = max(1.0, height_px * scale)

    writer = PdfWriter()
    page = writer.add_page(page_width, page_height)
    blob, filter_name = _embed_image(data, width_px, height_px)
    page.draw_image(
        PlacedImage(blob, width_px, height_px, filter_name),
        0.0, 0.0, page_width, page_height,
    )
    writer.write(output_path)
    return output_path


def _embed_image(data: bytes, width_px: int, height_px: int):
    """Return ``(stream_bytes, filter_name)`` for embedding raw image data."""
    if data.startswith(PNG_SIGNATURE):
        idat, color_type, bit_depth, interlace = _png_samples(data)
        if color_type == 2 and bit_depth == 8 and interlace == 0:
            return idat, "FlateDecode"
        if color_type == 6 and bit_depth == 8 and interlace == 0:
            # RGBA -> RGB; the alpha channel would otherwise render black.
            return _drop_alpha(idat, width_px, height_px), "FlateDecode"
        raise ImageError(
            "PNG yang belum didukung (hanya 8-bit RGB/RGBA non-interlaced). "
            "Simpan ulang sebagai JPEG untuk konversi ke PDF."
        )
    if data.startswith(b"\xff\xd8"):
        return data, "DCTDecode"
    raise ImageError("Format gambar tidak didukung; yang bisa dibaca: PNG dan JPEG.")


def _png_chunks(data: bytes):
    pos = len(PNG_SIGNATURE)
    end = len(data)
    while pos + 8 <= end:
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        yield tag, payload
        pos += 12 + length
        if tag == b"IEND":
            return


def _png_samples(data: bytes):
    color_type = bit_depth = interlace = 0
    idat = bytearray()
    for tag, payload in _png_chunks(data):
        if tag == b"IHDR" and len(payload) >= 13:
            _w, _h, bit_depth, color_type, _c, _f, interlace = struct.unpack(
                ">IIBBBBB", payload[:13])
        elif tag == b"IDAT":
            idat += payload
        elif tag == b"IEND":
            break
    return bytes(idat), color_type, bit_depth, interlace


def _drop_alpha(compressed_rgba: bytes, width_px: int, height_px: int) -> bytes:
    """Strip the alpha byte from each RGBA pixel of a non-interlaced PNG.

    Returns RGB samples compressed with Flate, matching what a PDF image XObject
    with ``/Filter /FlateDecode`` expects.
    """
    raw = zlib.decompress(compressed_rgba)
    stride = width_px * 4
    out = bytearray()
    previous = bytearray(stride)
    pos = 0
    for _ in range(height_px):
        if pos >= len(raw):
            break
        filter_type = raw[pos]
        pos += 1
        row = bytearray(raw[pos:pos + stride])
        if len(row) < stride:
            row += bytearray(stride - len(row))
        pos += stride
        _unfilter_row(filter_type, row, previous, 4)
        previous = row
        # Emit the row with filter 0 and RGB samples only.
        out.append(0)
        for x in range(width_px):
            base = x * 4
            out += row[base:base + 3]
    return zlib.compress(bytes(out), 6)


def _unfilter_row(filter_type: int, row: bytearray, previous: bytearray, bpp: int) -> None:
    """Undo a PNG row filter in place (mirrors the decoder in _filter.py)."""
    length = len(row)
    if filter_type == 0:
        return
    if filter_type == 1:
        for i in range(bpp, length):
            row[i] = (row[i] + row[i - bpp]) & 0xFF
    elif filter_type == 2:
        for i in range(length):
            row[i] = (row[i] + previous[i]) & 0xFF
    elif filter_type == 3:
        for i in range(length):
            left = row[i - bpp] if i >= bpp else 0
            row[i] = (row[i] + ((left + previous[i]) >> 1)) & 0xFF
    elif filter_type == 4:
        for i in range(length):
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


class ImageMetadata:
    """Extracted image metadata."""

    __slots__ = ("width", "height", "format", "color_space", "bit_depth", "file_size")

    def __init__(self, width: int, height: int, format: str, color_space: str = "RGB",
                 bit_depth: int = 8, file_size: int = 0):
        self.width = width
        self.height = height
        self.format = format
        self.color_space = color_space
        self.bit_depth = bit_depth
        self.file_size = file_size

    @property
    def aspect_ratio(self) -> float:
        """Width/height ratio."""
        return self.width / max(self.height, 1)

    @property
    def megapixels(self) -> float:
        """Total megapixels."""
        return (self.width * self.height) / 1e6

    def __repr__(self):
        return (f"<ImageMetadata {self.format} {self.width}x{self.height} "
                f"{self.color_space} {self.bit_depth}bit {self.file_size}B>")


def get_image_metadata(path_or_data) -> ImageMetadata:
    """Extract metadata from image file or bytes."""
    if isinstance(path_or_data, (str, Path)):
        path = Path(path_or_data)
        if not path.exists():
            raise ImageError(f"File tidak ditemukan: {path}")
        file_size = path.stat().st_size
        with open(path, "rb") as f:
            data = f.read()
    else:
        data = bytes(path_or_data)
        file_size = len(data)

    if data.startswith(PNG_SIGNATURE):
        return _parse_png_metadata(data, file_size)
    elif data.startswith(b"\xff\xd8"):
        return _parse_jpeg_metadata(data, file_size)
    else:
        raise ImageError("Format gambar tidak didukung; yang bisa dibaca: PNG dan JPEG.")


def _parse_png_metadata(data: bytes, file_size: int) -> ImageMetadata:
    """Extract PNG metadata from bytes."""
    try:
        for tag, payload in _png_chunks(data):
            if tag == b"IHDR" and len(payload) >= 13:
                width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", payload[:13])
                color_space = {0: "Grayscale", 2: "RGB", 3: "Indexed", 4: "Grayscale+Alpha", 6: "RGBA"}.get(color_type, "Unknown")
                return ImageMetadata(width, height, "PNG", color_space, bit_depth, file_size)
    except Exception:
        pass
    raise ImageError("PNG header tidak valid atau terpotong.")


def _parse_jpeg_metadata(data: bytes, file_size: int) -> ImageMetadata:
    """Extract JPEG metadata from bytes."""
    try:
        width, height = _jpeg_dimensions(data)
        # JPEG typically uses YCbCr color space
        return ImageMetadata(width, height, "JPEG", "YCbCr", 8, file_size)
    except Exception:
        pass
    raise ImageError("JPEG header tidak valid.")


def compress_image(image_data: bytes, quality: int = 85, max_width: int = None,
                   max_height: int = None) -> bytes:
    """Compress image, optionally resizing to fit bounds.

    For PNG: re-compress with zlib. For JPEG: already compressed.
    Resizing not supported without PIL; use for PNG re-compression only.
    """
    if quality < 1 or quality > 100:
        raise ImageError("Quality harus antara 1-100.")

    meta = get_image_metadata(image_data)

    if meta.format == "PNG":
        # Re-compress PNG with quality-based zlib level (1-9)
        zlib_level = max(1, min(9, (quality // 11)))
        return _recompress_png(image_data, zlib_level)
    elif meta.format == "JPEG":
        # JPEG already compressed; return as-is (no re-encoding without PIL)
        return image_data
    else:
        raise ImageError(f"Kompresi format {meta.format} belum didukung.")


def _recompress_png(data: bytes, zlib_level: int) -> bytes:
    """Re-compress PNG with specified zlib level."""
    new_data = bytearray(PNG_SIGNATURE)
    for tag, payload in _png_chunks(data):
        if tag == b"IDAT":
            # Re-decompress and re-compress with new level
            try:
                uncompressed = zlib.decompress(payload)
                compressed = zlib.compress(uncompressed, zlib_level)
                new_data += _chunk(tag, compressed)
            except Exception:
                # If decompression fails, keep original chunk
                new_data += _chunk(tag, payload)
        else:
            new_data += _chunk(tag, payload)
    return bytes(new_data)


def batch_process_images(image_paths: list, output_dir: str = None,
                        compress: bool = True, quality: int = 85) -> dict:
    """Process multiple images, optionally compressing.

    Returns dict with results: {path: (output_path, original_size, new_size, status)}
    """
    output_dir = Path(output_dir) if output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for img_path in image_paths:
        path = Path(img_path)
        if not path.exists():
            results[str(path)] = (None, 0, 0, f"File tidak ditemukan")
            continue

        try:
            original_size = path.stat().st_size
            with open(path, "rb") as f:
                data = f.read()

            if compress:
                compressed = compress_image(data, quality)
                output_path = output_dir / f"{path.stem}_compressed{path.suffix}"
                with open(output_path, "wb") as f:
                    f.write(compressed)
                new_size = len(compressed)
                status = f"Kompresi: {original_size} → {new_size}B"
            else:
                output_path = output_dir / path.name
                with open(output_path, "wb") as f:
                    f.write(data)
                new_size = original_size
                status = "Disalin"

            results[str(path)] = (str(output_path), original_size, new_size, status)
        except Exception as e:
            results[str(path)] = (None, 0, 0, f"Error: {str(e)}")

    return results


def image_stats(image_path) -> dict:
    """Get detailed image statistics."""
    meta = get_image_metadata(image_path)
    path = Path(image_path)

    return {
        "path": str(path),
        "filename": path.name,
        "format": meta.format,
        "width": meta.width,
        "height": meta.height,
        "megapixels": round(meta.megapixels, 2),
        "aspect_ratio": round(meta.aspect_ratio, 2),
        "color_space": meta.color_space,
        "bit_depth": meta.bit_depth,
        "file_size_bytes": meta.file_size,
        "file_size_mb": round(meta.file_size / (1024 * 1024), 3),
        "bytes_per_pixel": round(meta.file_size / (meta.width * meta.height), 2) if meta.width > 0 else 0,
    }


def write_jpeg(width: int, height: int, pixels: bytes, quality: int = 85) -> bytes:
    """Generate a JPEG from raw RGB pixels.

    JPEG encoding from scratch requires complex Huffman tables and DCT math.
    This is a limitation: JPEG writing needs external library (PIL) for quality control.
    For now, raise informative error directing to alternatives.
    """
    raise ImageError(
        "JPEG write tidak tersedia dalam stdlib. Opsi:\n"
        "1. Gunakan PIL/Pillow: pip install pillow\n"
        "2. Konversi ke PNG dulu: write_png(...)\n"
        "3. Gunakan image tool eksternal (convert, ffmpeg)"
    )


def save_jpeg(path: str, width: int, height: int, pixels: bytes, quality: int = 85) -> str:
    """Save JPEG file (requires PIL/Pillow).

    See write_jpeg() for alternatives.
    """
    _ = write_jpeg(width, height, pixels, quality)  # Will raise informative error
    return path  # Never reached


def jpeg_to_png(jpeg_path: str, output_path: str = None) -> str:
    """Convert JPEG to PNG for better compression/quality control.

    Reads JPEG, extracts pixel data (if possible), writes as PNG.
    Note: Requires external tool or PIL for actual pixel extraction.
    """
    path = Path(jpeg_path)
    if not path.exists():
        raise ImageError(f"File tidak ditemukan: {jpeg_path}")

    output_path = output_path or str(path.with_suffix(".png"))

    with open(jpeg_path, "rb") as f:
        jpeg_data = f.read()

    # For now, copy as-is (actual conversion needs PIL)
    raise ImageError(
        "JPEG→PNG conversion memerlukan PIL. Gunakan:\n"
        "  from PIL import Image\n"
        "  img = Image.open('input.jpg')\n"
        "  img.save('output.png')"
    )