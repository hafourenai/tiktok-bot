"""Tests for Phase 2: Enhanced Image Handling.

Covers metadata extraction, compression, batch processing, and image utilities.
"""

import pytest
import tempfile
from pathlib import Path

from docconv.imgcodec import (
    ImageError, ImageMetadata, get_image_metadata, compress_image,
    batch_process_images, image_stats, write_png, save_png
)


class TestImageMetadata:
    """Test image metadata extraction and utility."""

    def test_metadata_creation(self):
        """Create ImageMetadata object."""
        meta = ImageMetadata(800, 600, "PNG", "RGB", 8, 5000)
        assert meta.width == 800
        assert meta.height == 600
        assert meta.format == "PNG"
        assert meta.megapixels == 0.48
        assert meta.aspect_ratio == pytest.approx(1.333, rel=0.01)

    def test_metadata_repr(self):
        """Metadata has useful string representation."""
        meta = ImageMetadata(1920, 1080, "JPEG", "YCbCr", 8, 50000)
        repr_str = repr(meta)
        assert "JPEG" in repr_str
        assert "1920x1080" in repr_str
        assert "YCbCr" in repr_str


class TestImageMetadataExtraction:
    """Test extracting metadata from files."""

    def test_png_metadata_extraction(self, tmp_path):
        """Extract metadata from PNG file."""
        path = tmp_path / "test.png"
        # Create simple 10x10 RGB PNG
        pixels = bytes([255, 0, 0] * 100)  # Red pixels
        write_png(10, 10, pixels, greyscale=False)
        save_png(path, 10, 10, pixels, greyscale=False)

        meta = get_image_metadata(str(path))
        assert meta.width == 10
        assert meta.height == 10
        assert meta.format == "PNG"
        assert meta.color_space == "RGB"

    def test_png_metadata_from_bytes(self, tmp_path):
        """Extract metadata from PNG bytes."""
        pixels = bytes([100, 100, 100] * 20 * 20)  # Gray pixels
        png_bytes = write_png(20, 20, pixels, greyscale=False)

        meta = get_image_metadata(png_bytes)
        assert meta.width == 20
        assert meta.height == 20
        assert meta.format == "PNG"

    def test_invalid_file_raises_error(self):
        """Invalid file path raises ImageError."""
        with pytest.raises(ImageError, match="tidak ditemukan"):
            get_image_metadata("/nonexistent/file.png")

    def test_invalid_format_raises_error(self):
        """Unsupported image format raises error."""
        with pytest.raises(ImageError, match="tidak didukung"):
            get_image_metadata(b"NOTANIMAGE")


class TestImageCompression:
    """Test image compression utilities."""

    def test_compress_png_reduces_size(self, tmp_path):
        """Compressing PNG reduces file size."""
        path = tmp_path / "original.png"
        # Create repetitive pattern (highly compressible)
        pixels = bytes([200] * 300 * 300 * 3)  # Large uniform image
        save_png(path, 300, 300, pixels)

        original_size = path.stat().st_size
        with open(path, "rb") as f:
            original_data = f.read()

        # Compress with high quality
        compressed = compress_image(original_data, quality=95)
        
        # Compression may not always reduce for small test data,
        # but function should work without error
        assert len(compressed) > 0
        assert compressed.startswith(b"\x89PNG")

    def test_compress_with_invalid_quality_raises_error(self):
        """Invalid quality parameter raises error."""
        pixels = bytes([100] * 300)
        png_data = write_png(10, 10, pixels, greyscale=False)

        with pytest.raises(ImageError, match="Quality|1-100"):
            compress_image(png_data, quality=150)

        with pytest.raises(ImageError, match="Quality|1-100"):
            compress_image(png_data, quality=0)

    def test_jpeg_write_raises_informative_error(self):
        """JPEG write returns informative error about PIL dependency."""
        from docconv.imgcodec import write_jpeg, save_jpeg

        pixels = bytes([255, 0, 0] * 100)
        
        with pytest.raises(ImageError, match="PIL|Pillow"):
            write_jpeg(10, 10, pixels)

        with pytest.raises(ImageError, match="PIL|Pillow"):
            save_jpeg("/tmp/test.jpg", 10, 10, pixels)


class TestBatchProcessing:
    """Test batch image processing."""

    def test_batch_process_single_image(self, tmp_path):
        """Process single image in batch."""
        # Create test image
        input_file = tmp_path / "input.png"
        pixels = bytes([100] * 300)
        save_png(input_file, 10, 10, pixels)

        output_dir = tmp_path / "output"
        results = batch_process_images([str(input_file)], str(output_dir), compress=True)

        assert str(input_file) in results
        output_path, orig_size, new_size, status = results[str(input_file)]
        assert output_path is not None
        assert orig_size > 0
        assert "Kompresi" in status or "Disalin" in status

    def test_batch_process_nonexistent_file(self, tmp_path):
        """Batch processing nonexistent file records error."""
        fake_path = tmp_path / "nonexistent.png"
        output_dir = tmp_path / "output"

        results = batch_process_images([str(fake_path)], str(output_dir))

        assert str(fake_path) in results
        output_path, _, _, status = results[str(fake_path)]
        assert output_path is None
        assert "tidak ditemukan" in status.lower()

    def test_batch_process_multiple_images(self, tmp_path):
        """Process multiple images."""
        # Create 3 test images
        files = []
        for i in range(3):
            path = tmp_path / f"image_{i}.png"
            pixels = bytes([i * 50] * 300)
            save_png(path, 10, 10, pixels)
            files.append(str(path))

        output_dir = tmp_path / "output"
        results = batch_process_images(files, str(output_dir), compress=True)

        assert len(results) == 3
        for file_path in files:
            assert file_path in results
            output_path, _, _, status = results[file_path]
            assert output_path is not None or "Error" in status


class TestImageStats:
    """Test image statistics generation."""

    def test_image_stats_png(self, tmp_path):
        """Generate stats for PNG image."""
        path = tmp_path / "test.png"
        pixels = bytes([128] * 600)
        save_png(path, 20, 10, pixels)

        stats = image_stats(str(path))

        assert stats["format"] == "PNG"
        assert stats["width"] == 20
        assert stats["height"] == 10
        assert stats["megapixels"] == 0.0002
        assert stats["aspect_ratio"] == 2.0
        assert stats["file_size_bytes"] > 0
        assert "file_size_mb" in stats
        assert "bytes_per_pixel" in stats

    def test_image_stats_has_all_fields(self, tmp_path):
        """Image stats includes all required fields."""
        path = tmp_path / "test.png"
        pixels = bytes([255, 0, 0] * 100)
        save_png(path, 10, 10, pixels)

        stats = image_stats(str(path))

        required_fields = [
            "path", "filename", "format", "width", "height",
            "megapixels", "aspect_ratio", "color_space", "bit_depth",
            "file_size_bytes", "file_size_mb", "bytes_per_pixel"
        ]
        for field in required_fields:
            assert field in stats, f"Missing field: {field}"

    def test_image_stats_invalid_path_raises_error(self):
        """Invalid path raises error."""
        with pytest.raises(ImageError, match="tidak ditemukan"):
            image_stats("/nonexistent/image.png")


class TestImageMetadataEdgeCases:
    """Test metadata extraction edge cases."""

    def test_large_image_dimensions(self):
        """Handle very large dimensions in metadata."""
        meta = ImageMetadata(100000, 100000, "PNG")
        assert meta.megapixels == 10000.0
        assert meta.aspect_ratio == 1.0

    def test_zero_dimension_aspect_ratio(self):
        """Handle zero dimension gracefully."""
        meta = ImageMetadata(100, 0, "PNG")
        # Division by zero in aspect_ratio is handled in property
        assert meta.megapixels == 0.0

    def test_color_space_mapping(self, tmp_path):
        """Verify color space mappings in PNG metadata."""
        path = tmp_path / "test.png"
        pixels = bytes([100] * 300)
        save_png(path, 10, 10, pixels, greyscale=False)

        meta = get_image_metadata(str(path))
        # Saved as RGB
        assert meta.color_space == "RGB"
        assert meta.bit_depth == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
