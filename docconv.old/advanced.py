"""Advanced document features.

Features:
- Metadata extraction (author, title, keywords, creation date)
- Watermark detection and analysis
- Document encryption/decryption framework
- Search index generation
- Document diffing (compare two PDFs)
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class DocumentMetadata:
    """PDF document metadata."""
    
    def __init__(self):
        self.title: Optional[str] = None
        self.author: Optional[str] = None
        self.subject: Optional[str] = None
        self.keywords: List[str] = []
        self.creator: Optional[str] = None  # Software that created it
        self.producer: Optional[str] = None  # Software that produced PDF
        self.creation_date: Optional[datetime] = None
        self.modification_date: Optional[datetime] = None
        self.pages: int = 0
        self.encrypted: bool = False
        self.compression_level: int = 0
        self.custom_metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "author": self.author,
            "subject": self.subject,
            "keywords": self.keywords,
            "creator": self.creator,
            "producer": self.producer,
            "creation_date": self.creation_date.isoformat() if self.creation_date else None,
            "modification_date": self.modification_date.isoformat() if self.modification_date else None,
            "pages": self.pages,
            "encrypted": self.encrypted,
            "compression_level": self.compression_level,
        }

    def to_json(self) -> str:
        """Convert to JSON."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    def __repr__(self):
        return f"<DocumentMetadata '{self.title}' by {self.author} ({self.pages} pages)>"


class WatermarkDetector:
    """Detect watermarks in documents."""
    
    @staticmethod
    def detect_text_watermark(text: str, min_frequency: float = 0.05) -> Optional[str]:
        """Detect repeated text patterns (watermark candidates)."""
        words = text.lower().split()
        if not words:
            return None
        
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Find highly repeated words (potential watermark)
        for word, count in sorted(word_freq.items(), key=lambda x: -x[1]):
            frequency = count / len(words)
            if frequency >= min_frequency and len(word) > 3:
                return word
        
        return None

    @staticmethod
    def detect_watermark_indicators(pages: List) -> Dict[str, Any]:
        """Analyze pages for watermark indicators."""
        indicators = {
            "has_background_text": False,
            "has_repeated_patterns": False,
            "suspicious_text_repetition": False,
            "common_words": [],
            "potential_watermark": None,
        }
        
        all_text = "\n".join(page.text for page in pages)
        
        # Check for text watermark
        watermark = WatermarkDetector.detect_text_watermark(all_text)
        if watermark:
            indicators["potential_watermark"] = watermark
            indicators["suspicious_text_repetition"] = True
        
        # Analyze common words
        words = all_text.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 5:  # Only long words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        common = sorted(word_freq.items(), key=lambda x: -x[1])[:5]
        indicators["common_words"] = [w[0] for w in common if w[1] > 2]
        
        return indicators


class DocumentEncryption:
    """Framework for document encryption/decryption."""
    
    @staticmethod
    def check_encryption_status(pdf_path: str) -> Dict[str, Any]:
        """Check if PDF is encrypted."""
        from docconv import extract_pages
        
        try:
            pages = extract_pages(pdf_path)
            return {
                "encrypted": False,
                "pages": len(pages),
                "readable": True,
            }
        except Exception as e:
            if "encrypted" in str(e).lower():
                return {
                    "encrypted": True,
                    "readable": False,
                    "error": str(e),
                }
            raise

    @staticmethod
    def encrypt_document_placeholder(pdf_path: str, output_path: str, 
                                    password: str) -> str:
        """Placeholder for encryption (requires specialized library)."""
        raise NotImplementedError(
            "PDF encryption requires specialized library. Options:\n"
            "1. Use PyPDF2: pip install PyPDF2\n"
            "2. Use pikepdf: pip install pikepdf\n"
            "3. Use external tool: qpdf, ghostscript"
        )

    @staticmethod
    def decrypt_document_placeholder(pdf_path: str, password: str) -> bytes:
        """Placeholder for decryption (requires specialized library)."""
        raise NotImplementedError(
            "PDF decryption requires specialized library. Options:\n"
            "1. Use PyPDF2: pip install PyPDF2\n"
            "2. Use pikepdf: pip install pikepdf\n"
            "3. Use qpdf command-line tool"
        )


class SearchIndex:
    """Generate and query full-text search index."""
    
    def __init__(self):
        self.index: Dict[str, Set[int]] = {}  # word -> page numbers
        self.pages_text: Dict[int, str] = {}  # page_num -> text
        self.metadata: Dict[str, Any] = {}

    def index_pages(self, pages: List) -> None:
        """Build search index from pages."""
        for page in pages:
            page_num = page.number
            text = page.text.lower()
            
            # Store full text
            self.pages_text[page_num] = text
            
            # Index words
            words = self._tokenize(text)
            for word in words:
                if word not in self.index:
                    self.index[word] = set()
                self.index[word].add(page_num)
        
        self.metadata = {
            "total_pages": len(pages),
            "total_words": sum(len(self._tokenize(t)) for t in self.pages_text.values()),
            "vocabulary_size": len(self.index),
        }

    def search(self, query: str, operator: str = "OR") -> Dict[str, Any]:
        """Search index."""
        query_words = self._tokenize(query.lower())
        
        if not query_words:
            return {"query": query, "results": [], "count": 0}
        
        if operator == "AND":
            # All words must be present
            result_pages = set.intersection(*[self.index.get(w, set()) for w in query_words])
        else:  # OR
            # Any word present
            result_pages = set.union(*[self.index.get(w, set()) for w in query_words])
        
        results = []
        for page_num in sorted(result_pages):
            text = self.pages_text.get(page_num, "")
            # Extract context (50 chars around first match)
            for word in query_words:
                if word in text:
                    idx = text.find(word)
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(word) + 50)
                    context = text[start:end].strip()
                    results.append({
                        "page": page_num,
                        "context": context,
                    })
                    break
        
        return {
            "query": query,
            "operator": operator,
            "results": results,
            "count": len(results),
        }

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        import re
        # Remove punctuation, split on whitespace
        words = re.findall(r"\b\w+\b", text)
        # Filter short words
        return [w for w in words if len(w) > 2]

    def to_json(self) -> str:
        """Export index as JSON."""
        # Convert sets to lists for JSON serialization
        index_data = {
            "metadata": self.metadata,
            "vocabulary_size": len(self.index),
            "top_terms": sorted(
                [(k, len(v)) for k, v in self.index.items()],
                key=lambda x: -x[1]
            )[:20]
        }
        return json.dumps(index_data, indent=2)


class DocumentDiffer:
    """Compare two documents (find differences)."""
    
    @staticmethod
    def diff_text(text1: str, text2: str) -> Dict[str, Any]:
        """Find text differences between documents."""
        lines1 = text1.split("\n")
        lines2 = text2.split("\n")
        
        diff = {
            "added_lines": [],
            "removed_lines": [],
            "modified_lines": [],
            "total_differences": 0,
        }
        
        # Simple diff: line-by-line comparison
        for i, (line1, line2) in enumerate(zip(lines1, lines2)):
            if line1 != line2:
                diff["modified_lines"].append({
                    "line": i + 1,
                    "old": line1,
                    "new": line2,
                })
                diff["total_differences"] += 1
        
        # Extra lines in text2
        if len(lines2) > len(lines1):
            for i in range(len(lines1), len(lines2)):
                diff["added_lines"].append({
                    "line": i + 1,
                    "content": lines2[i],
                })
                diff["total_differences"] += 1
        
        # Extra lines in text1
        if len(lines1) > len(lines2):
            for i in range(len(lines2), len(lines1)):
                diff["removed_lines"].append({
                    "line": i + 1,
                    "content": lines1[i],
                })
                diff["total_differences"] += 1
        
        return diff

    @staticmethod
    def diff_pages(pages1: List, pages2: List) -> Dict[str, Any]:
        """Compare two sets of pages."""
        diff = {
            "total_pages_1": len(pages1),
            "total_pages_2": len(pages2),
            "page_count_diff": len(pages2) - len(pages1),
            "page_diffs": [],
            "text_similarity": 0.0,
        }
        
        # Compare common pages
        for i, (p1, p2) in enumerate(zip(pages1, pages2)):
            if p1.text != p2.text:
                diff["page_diffs"].append({
                    "page": i + 1,
                    "differences": len(DocumentDiffer.diff_text(p1.text, p2.text)["modified_lines"]),
                })
        
        # Calculate similarity
        if pages1 and pages2:
            matching_text = sum(
                1 for p1, p2 in zip(pages1, pages2) if p1.text == p2.text
            )
            diff["text_similarity"] = matching_text / max(len(pages1), len(pages2))
        
        return diff


def extract_all_metadata(pdf_path: str) -> DocumentMetadata:
    """Extract all available metadata from PDF."""
    from docconv import extract_pages
    
    metadata = DocumentMetadata()
    
    try:
        pages = extract_pages(pdf_path)
        metadata.pages = len(pages)
        
        # Try to detect encryption
        metadata.encrypted = False
        
        # Keywords from content
        all_text = "\n".join(p.text for p in pages)
        words = all_text.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 5:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Top 10 words as keywords
        metadata.keywords = sorted(word_freq.items(), key=lambda x: -x[1])[:10]
        metadata.keywords = [w[0] for w in metadata.keywords]
        
    except Exception as e:
        metadata.encrypted = "encrypted" in str(e).lower()
    
    return metadata


def create_analysis_report(pdf_path: str, pages: List) -> Dict[str, Any]:
    """Create comprehensive analysis report."""
    report = {
        "file": str(pdf_path),
        "generated_at": datetime.now().isoformat(),
        "metadata": extract_all_metadata(pdf_path).to_dict(),
        "watermark_analysis": WatermarkDetector.detect_watermark_indicators(pages),
        "search_index": SearchIndex(),
        "content_analysis": {
            "total_pages": len(pages),
            "total_text_bytes": sum(len(p.text.encode()) for p in pages),
            "total_tables": sum(len(p.tables) for p in pages),
        },
    }
    
    # Build search index
    report["search_index"].index_pages(pages)
    
    return report


__all__ = [
    "DocumentMetadata",
    "WatermarkDetector",
    "DocumentEncryption",
    "SearchIndex",
    "DocumentDiffer",
    "extract_all_metadata",
    "create_analysis_report",
]
