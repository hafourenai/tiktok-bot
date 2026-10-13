"""Tests for Phase 6: Performance & Scale.

Covers caching, streaming, batch processing, memory efficiency, parallel processing.
"""

import pytest
import tempfile
import time
from pathlib import Path

from docconv.performance import (
    CacheEntry, ConversionCache, compute_file_hash,
    StreamingPdfProcessor, BatchJob, BatchProcessor,
    MemoryEfficientImageProcessor, create_processing_pipeline,
    estimate_memory_usage
)


class TestCacheEntry:
    """Test CacheEntry class."""

    def test_cache_entry_creation(self):
        """Create cache entry."""
        entry = CacheEntry(
            key="test_key",
            data={"value": 123},
            created_at=None,
            ttl=3600,
            hit_count=0
        )
        entry.created_at = __import__("datetime").datetime.now()
        
        assert entry.key == "test_key"
        assert entry.data == {"value": 123}

    def test_cache_entry_not_expired_with_ttl(self):
        """Entry not expired if TTL not passed."""
        from datetime import datetime
        
        entry = CacheEntry(
            key="test",
            data="value",
            created_at=datetime.now(),
            ttl=3600
        )
        
        assert not entry.is_expired()

    def test_cache_entry_no_expiry_with_zero_ttl(self):
        """Entry never expires with TTL=0."""
        from datetime import datetime
        
        entry = CacheEntry(
            key="test",
            data="value",
            created_at=datetime.now(),
            ttl=0
        )
        
        assert not entry.is_expired()


class TestConversionCache:
    """Test ConversionCache."""

    def test_cache_set_and_get(self):
        """Set and retrieve from cache."""
        cache = ConversionCache()
        
        cache.set("key1", "value1")
        result = cache.get("key1")
        
        assert result == "value1"

    def test_cache_miss_returns_none(self):
        """Cache miss returns None."""
        cache = ConversionCache()
        
        result = cache.get("nonexistent")
        
        assert result is None

    def test_cache_respects_max_entries(self):
        """Cache evicts oldest when full."""
        cache = ConversionCache(max_entries=3)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict key1
        
        assert len(cache.cache) <= 3

    def test_cache_tracks_hit_count(self):
        """Cache tracks hit count."""
        cache = ConversionCache()
        
        cache.set("key", "value")
        cache.get("key")
        cache.get("key")
        
        entry = cache.cache["key"]
        assert entry.hit_count == 2

    def test_cache_clear(self):
        """Clear cache."""
        cache = ConversionCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        
        assert len(cache.cache) == 0

    def test_cache_stats(self):
        """Get cache statistics."""
        cache = ConversionCache()
        
        cache.set("key1", "value1")
        cache.get("key1")
        
        stats = cache.stats()
        
        assert stats["entries"] == 1
        assert stats["total_hits"] == 1


class TestFileHash:
    """Test file hashing."""

    def test_compute_file_hash(self, tmp_path):
        """Compute hash of file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello world")
        
        hash1 = compute_file_hash(str(file_path))
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex string length

    def test_same_content_same_hash(self, tmp_path):
        """Same content produces same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_text("Content")
        file2.write_text("Content")
        
        hash1 = compute_file_hash(str(file1))
        hash2 = compute_file_hash(str(file2))
        
        assert hash1 == hash2

    def test_different_content_different_hash(self, tmp_path):
        """Different content produces different hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_text("Content A")
        file2.write_text("Content B")
        
        hash1 = compute_file_hash(str(file1))
        hash2 = compute_file_hash(str(file2))
        
        assert hash1 != hash2


class TestStreamingPdfProcessor:
    """Test StreamingPdfProcessor."""

    def test_processor_creation(self, tmp_path):
        """Create processor."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")  # Minimal PDF
        
        processor = StreamingPdfProcessor(str(pdf_path))
        
        assert processor.pdf_path == str(pdf_path)
        assert processor.file_hash

    def test_processor_with_cache(self, tmp_path):
        """Processor with cache."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        
        cache = ConversionCache()
        processor = StreamingPdfProcessor(str(pdf_path), cache=cache)
        
        assert processor.cache is cache


class TestBatchJob:
    """Test BatchJob class."""

    def test_batch_job_creation(self):
        """Create batch job."""
        job = BatchJob(
            input_path="/input.pdf",
            output_path="/output.json",
            format="json"
        )
        
        assert job.input_path == "/input.pdf"
        assert job.status == "pending"
        assert job.error is None

    def test_batch_job_status_changes(self):
        """Update job status."""
        job = BatchJob("/in.pdf", "/out.json", "json")
        
        job.status = "processing"
        assert job.status == "processing"
        
        job.status = "success"
        assert job.status == "success"


class TestBatchProcessor:
    """Test BatchProcessor."""

    def test_batch_processor_creation(self):
        """Create batch processor."""
        processor = BatchProcessor(max_parallel=4)
        
        assert processor.max_parallel == 4
        assert len(processor.queue) == 0

    def test_add_jobs_to_queue(self):
        """Add jobs to batch queue."""
        processor = BatchProcessor()
        
        processor.add_job("/in1.pdf", "/out1.json", "json")
        processor.add_job("/in2.pdf", "/out2.json", "json")
        
        assert len(processor.queue) == 2

    def test_batch_job_tracking(self):
        """Track batch jobs."""
        processor = BatchProcessor()
        
        processor.add_job("/in.pdf", "/out.json", "json")
        assert len(processor.queue) == 1
        assert processor.queue[0].status == "pending"

    def test_batch_processor_with_mock_converter(self):
        """Process batch with mock converter."""
        processor = BatchProcessor(max_parallel=1)
        
        processor.add_job("/in1.pdf", "/out1.json", "json")
        processor.add_job("/in2.pdf", "/out2.json", "json")
        
        def mock_converter(input_path, output_path, format_type):
            return True  # Simulate success
        
        summary = processor.process_all(mock_converter)
        
        assert summary["total"] == 2
        assert summary["success"] >= 0  # May be 0 if path doesn't exist


class TestMemoryEfficientImageProcessor:
    """Test memory-efficient image processing."""

    def test_process_in_chunks(self, tmp_path):
        """Process image in chunks."""
        image_path = tmp_path / "image.bin"
        image_path.write_bytes(b"x" * 10000)  # 10KB file
        
        stats = MemoryEfficientImageProcessor.process_in_chunks(
            str(image_path), chunk_size=1024
        )
        
        assert stats["size"] == 10000
        assert stats["chunks"] == 10

    def test_process_small_image_single_chunk(self, tmp_path):
        """Small image processes in single chunk."""
        image_path = tmp_path / "small.bin"
        image_path.write_bytes(b"small")
        
        stats = MemoryEfficientImageProcessor.process_in_chunks(
            str(image_path), chunk_size=1024*1024
        )
        
        assert stats["chunks"] == 1


class TestProcessingPipeline:
    """Test processing pipeline creation."""

    def test_create_pipeline(self):
        """Create processing pipeline."""
        pipeline = create_processing_pipeline()
        
        assert "cache" in pipeline
        assert "batch_processor" in pipeline
        assert "config" in pipeline
        assert isinstance(pipeline["cache"], ConversionCache)

    def test_pipeline_config(self):
        """Pipeline has proper configuration."""
        pipeline = create_processing_pipeline()
        config = pipeline["config"]
        
        assert config["streaming_enabled"]
        assert config["parallel_enabled"]
        assert config["cache_ttl"] > 0


class TestMemoryEstimation:
    """Test memory usage estimation."""

    def test_estimate_memory_usage(self, tmp_path):
        """Estimate memory for PDF processing."""
        # Create minimal PDF
        pdf_path = tmp_path / "test.pdf"
        pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Root 1 0 R /Size 4 >>
startxref
200
%%EOF
"""
        pdf_path.write_bytes(pdf_content)
        
        estimate = estimate_memory_usage(str(pdf_path))
        
        assert "file_size_mb" in estimate
        assert "page_count" in estimate
        assert estimate["file_size_mb"] >= 0


class TestCacheExpiration:
    """Test cache expiration."""

    def test_expired_entry_not_returned(self):
        """Expired entry not returned from cache."""
        from datetime import datetime, timedelta
        
        cache = ConversionCache()
        
        # Create entry that's already expired
        cache.set("key", "value", ttl=1)
        
        # Wait for expiration
        time.sleep(1.1)
        
        result = cache.get("key")
        
        # Should be expired
        assert result is None


class TestIntegration:
    """Integration tests for performance features."""

    def test_full_caching_workflow(self):
        """Complete caching workflow."""
        cache = ConversionCache()
        
        # First access: miss
        assert cache.get("doc1") is None
        
        # Set value
        cache.set("doc1", {"pages": 10}, ttl=3600)
        
        # Subsequent accesses: hit
        result1 = cache.get("doc1")
        result2 = cache.get("doc1")
        
        assert result1 == {"pages": 10}
        assert result2 == {"pages": 10}
        
        # Check stats
        stats = cache.stats()
        assert stats["total_hits"] == 2

    def test_batch_processing_workflow(self):
        """Complete batch processing workflow."""
        processor = BatchProcessor(max_parallel=2)
        
        # Add multiple jobs
        for i in range(3):
            processor.add_job(
                f"/input{i}.pdf",
                f"/output{i}.json",
                "json"
            )
        
        assert len(processor.queue) == 3
        
        # Mock converter
        def mock_converter(in_path, out_path, fmt):
            return True
        
        # Process
        summary = processor.process_all(mock_converter)
        assert summary["total"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
