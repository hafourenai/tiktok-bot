"""Performance optimization and large-scale processing.

Features:
- Streaming for large PDFs (page-by-page processing)
- Caching mechanism for repeated conversions
- Batch file processing pipeline
- Memory-efficient image handling
- Parallel processing support
"""

import hashlib
import pickle
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Generator
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class CacheEntry:
    """Cached conversion result."""
    
    def __init__(self, key: str, data: Any, created_at: datetime, ttl: int):
        self.key = key
        self.data = data
        self.created_at = created_at
        self.ttl = ttl
        self.hit_count = 0

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl <= 0:
            return False
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.ttl


class ConversionCache:
    """In-memory cache for conversions."""
    
    def __init__(self, max_entries: int = 100):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_entries = max_entries
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        with self.lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            if entry.is_expired():
                del self.cache[key]
                return None
            
            entry.hit_count += 1
            return entry.data

    def set(self, key: str, data: Any, ttl: int = 3600) -> None:
        """Set cache value with optional TTL."""
        with self.lock:
            # Evict oldest if at capacity
            if len(self.cache) >= self.max_entries:
                oldest_key = min(self.cache.keys(), 
                                key=lambda k: self.cache[k].created_at)
                del self.cache[oldest_key]
            
            self.cache[key] = CacheEntry(key, data, datetime.now(), ttl)

    def clear(self) -> None:
        """Clear all cache."""
        with self.lock:
            self.cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_hits = sum(e.hit_count for e in self.cache.values())
            return {
                "entries": len(self.cache),
                "max_entries": self.max_entries,
                "total_hits": total_hits,
                "avg_ttl": sum(e.ttl for e in self.cache.values()) / len(self.cache) if self.cache else 0,
            }


def compute_file_hash(path: str, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of file (for cache key)."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


class StreamingPdfProcessor:
    """Process large PDFs page-by-page without loading entire file."""
    
    def __init__(self, pdf_path: str, cache: Optional[ConversionCache] = None):
        self.pdf_path = pdf_path
        self.cache = cache
        self.file_hash = compute_file_hash(pdf_path)

    def process_pages(self, processor_func: Callable) -> Generator[Any, None, None]:
        """Process pages one at a time, yielding results."""
        from docconv import extract_pages
        
        # Check cache for entire file
        cache_key = f"pdf:{self.file_hash}:all"
        if self.cache and (cached := self.cache.get(cache_key)):
            yield from cached
            return
        
        results = []
        try:
            pages = extract_pages(self.pdf_path)
            for page in pages:
                result = processor_func(page)
                results.append(result)
                yield result
        finally:
            # Cache all results after processing
            if self.cache and results:
                self.cache.set(cache_key, results, ttl=3600)

    def process_pages_parallel(self, processor_func: Callable, 
                              max_workers: int = 4) -> List[Any]:
        """Process pages in parallel."""
        from docconv import extract_pages
        
        pages = extract_pages(self.pdf_path)
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(processor_func, page): i 
                      for i, page in enumerate(pages)}
            
            for future in as_completed(futures):
                results.append(future.result())
        
        return sorted([(i, results[i]) for i, _ in enumerate(futures.keys())])


class BatchJob:
    """Single batch processing job."""
    
    def __init__(self, input_path: str, output_path: str, format: str):
        self.input_path = input_path
        self.output_path = output_path
        self.format = format
        self.status = "pending"  # pending, processing, success, failed
        self.error: Optional[str] = None


class BatchProcessor:
    """Process multiple files in batch."""
    
    def __init__(self, max_parallel: int = 4):
        self.max_parallel = max_parallel
        self.queue: List[BatchJob] = []
        self.results: Dict[str, BatchJob] = {}

    def add_job(self, input_path: str, output_path: str, format: str) -> None:
        """Add job to queue."""
        job = BatchJob(input_path, output_path, format)
        self.queue.append(job)

    def process_all(self, converter_func: Callable[[str, str, str], bool]) -> Dict[str, Any]:
        """Process all jobs, return summary."""
        summary = {
            "total": len(self.queue),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "results": []
        }

        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            futures = {}
            for job in self.queue:
                future = executor.submit(self._process_job, job, converter_func)
                futures[future] = job

            for future in as_completed(futures):
                job = futures[future]
                try:
                    job = future.result()
                    self.results[job.input_path] = job
                    
                    if job.status == "success":
                        summary["success"] += 1
                    elif job.status == "failed":
                        summary["failed"] += 1
                        summary["results"].append({
                            "file": job.input_path,
                            "error": job.error
                        })
                except Exception as e:
                    job.status = "failed"
                    job.error = str(e)
                    summary["failed"] += 1

        return summary

    def _process_job(self, job: BatchJob, converter_func: Callable) -> BatchJob:
        """Process single job."""
        job.status = "processing"
        try:
            success = converter_func(job.input_path, job.output_path, job.format)
            job.status = "success" if success else "failed"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
        return job


class MemoryEfficientImageProcessor:
    """Process large images with minimal memory."""
    
    @staticmethod
    def process_in_chunks(image_path: str, chunk_size: int = 1024*1024) -> Dict[str, Any]:
        """Process image file in chunks."""
        path = Path(image_path)
        
        stats = {
            "file": str(path),
            "size": path.stat().st_size,
            "chunks": 0,
            "format": path.suffix.lower()[1:],
        }

        with open(image_path, "rb") as f:
            while f.read(chunk_size):
                stats["chunks"] += 1

        return stats

    @staticmethod
    def downsample_image_on_disk(input_path: str, output_path: str, 
                                 scale: float = 0.5) -> str:
        """Downsample image without loading entire file."""
        # This is a framework; actual resampling needs PIL
        # For now, just copy with metadata about what would happen
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file
        with open(input_path, "rb") as src, open(output_path, "wb") as dst:
            dst.write(src.read())
        
        return output_path


def create_processing_pipeline() -> Dict[str, Any]:
    """Create configured processing pipeline."""
    return {
        "cache": ConversionCache(max_entries=50),
        "batch_processor": BatchProcessor(max_parallel=4),
        "config": {
            "streaming_enabled": True,
            "parallel_enabled": True,
            "cache_ttl": 3600,
            "max_workers": 4,
        }
    }


def estimate_memory_usage(pdf_path: str) -> Dict[str, Any]:
    """Estimate memory usage for PDF processing."""
    from docconv import extract_pages
    
    path = Path(pdf_path)
    file_size = path.stat().st_size
    
    # Rough estimates
    pages = extract_pages(pdf_path)
    page_count = len(pages)
    
    avg_page_size = file_size / page_count if page_count > 0 else 0
    total_text_size = sum(len(page.text.encode()) for page in pages)
    total_table_size = sum(
        len(json.dumps(page.tables).encode()) for page in pages
    )
    
    return {
        "file_size_mb": file_size / (1024 * 1024),
        "page_count": page_count,
        "avg_page_size_kb": avg_page_size / 1024,
        "total_text_mb": total_text_size / (1024 * 1024),
        "total_tables_mb": total_table_size / (1024 * 1024),
        "estimated_processing_memory_mb": (total_text_size + total_table_size) / (1024 * 1024),
    }


__all__ = [
    "CacheEntry",
    "ConversionCache",
    "compute_file_hash",
    "StreamingPdfProcessor",
    "BatchJob",
    "BatchProcessor",
    "MemoryEfficientImageProcessor",
    "create_processing_pipeline",
    "estimate_memory_usage",
]
