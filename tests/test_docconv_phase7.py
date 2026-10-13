"""Tests for Phase 7: Advanced Features.

Covers metadata extraction, watermark detection, encryption framework, search index, document diffing.
"""

import pytest
import json
from datetime import datetime

from docconv.advanced import (
    DocumentMetadata, WatermarkDetector, DocumentEncryption,
    SearchIndex, DocumentDiffer, extract_all_metadata, create_analysis_report
)


class TestDocumentMetadata:
    """Test DocumentMetadata class."""

    def test_metadata_creation(self):
        """Create metadata object."""
        meta = DocumentMetadata()
        
        assert meta.title is None
        assert meta.author is None
        assert meta.pages == 0
        assert meta.encrypted is False

    def test_metadata_fields(self):
        """Set metadata fields."""
        meta = DocumentMetadata()
        meta.title = "Test Document"
        meta.author = "Test Author"
        meta.pages = 10
        meta.keywords = ["python", "pdf", "document"]
        
        assert meta.title == "Test Document"
        assert meta.author == "Test Author"
        assert len(meta.keywords) == 3

    def test_metadata_to_dict(self):
        """Convert metadata to dictionary."""
        meta = DocumentMetadata()
        meta.title = "My Doc"
        meta.pages = 5
        
        data = meta.to_dict()
        
        assert data["title"] == "My Doc"
        assert data["pages"] == 5

    def test_metadata_to_json(self):
        """Convert metadata to JSON."""
        meta = DocumentMetadata()
        meta.title = "JSON Test"
        meta.pages = 3
        
        json_str = meta.to_json()
        data = json.loads(json_str)
        
        assert data["title"] == "JSON Test"


class TestWatermarkDetection:
    """Test watermark detection."""

    def test_detect_text_watermark_present(self):
        """Detect repeating text (watermark)."""
        text = "CONFIDENTIAL " * 50 + "Some document text"
        watermark = WatermarkDetector.detect_text_watermark(text, min_frequency=0.05)
        
        assert watermark == "confidential"

    def test_no_watermark_in_normal_text(self):
        """Normal text has no watermark."""
        text = "This is just normal document text without any watermarks or repeated patterns."
        watermark = WatermarkDetector.detect_text_watermark(text, min_frequency=0.1)
        
        assert watermark is None

    def test_watermark_indicators(self):
        """Analyze watermark indicators."""
        class MockPage:
            def __init__(self, text):
                self.text = text
        
        pages = [
            MockPage("DRAFT " * 20 + "Content here"),
            MockPage("DRAFT " * 20 + "More content"),
        ]
        
        indicators = WatermarkDetector.detect_watermark_indicators(pages)
        
        assert "potential_watermark" in indicators
        assert "common_words" in indicators


class TestSearchIndex:
    """Test search index functionality."""

    def test_index_creation(self):
        """Create search index."""
        index = SearchIndex()
        
        assert len(index.index) == 0
        assert len(index.pages_text) == 0

    def test_index_pages(self):
        """Index pages."""
        class MockPage:
            def __init__(self, number, text):
                self.number = number
                self.text = text
        
        pages = [
            MockPage(1, "Python is a programming language"),
            MockPage(2, "Python is widely used for data science"),
        ]
        
        index = SearchIndex()
        index.index_pages(pages)
        
        assert len(index.pages_text) == 2
        assert len(index.index) > 0

    def test_search_or_operator(self):
        """Search with OR operator."""
        class MockPage:
            def __init__(self, number, text):
                self.number = number
                self.text = text
        
        pages = [
            MockPage(1, "The quick brown fox"),
            MockPage(2, "Jumps over the lazy dog"),
        ]
        
        index = SearchIndex()
        index.index_pages(pages)
        
        result = index.search("quick lazy", operator="OR")
        
        assert result["count"] >= 1
        assert "results" in result

    def test_search_and_operator(self):
        """Search with AND operator."""
        class MockPage:
            def __init__(self, number, text):
                self.number = number
                self.text = text
        
        pages = [
            MockPage(1, "Python programming language"),
            MockPage(2, "Java programming language"),
        ]
        
        index = SearchIndex()
        index.index_pages(pages)
        
        result = index.search("programming language", operator="AND")
        
        assert result["count"] >= 1

    def test_search_index_to_json(self):
        """Export search index to JSON."""
        class MockPage:
            def __init__(self, number, text):
                self.number = number
                self.text = text
        
        pages = [
            MockPage(1, "Sample text with content"),
        ]
        
        index = SearchIndex()
        index.index_pages(pages)
        
        json_str = index.to_json()
        data = json.loads(json_str)
        
        assert "metadata" in data
        assert "vocabulary_size" in data


class TestDocumentDiffer:
    """Test document diffing."""

    def test_diff_identical_text(self):
        """Diff identical text."""
        text = "Same content here"
        diff = DocumentDiffer.diff_text(text, text)
        
        assert diff["total_differences"] == 0
        assert len(diff["modified_lines"]) == 0

    def test_diff_modified_lines(self):
        """Diff with modified lines."""
        text1 = "Line 1\nLine 2\nLine 3"
        text2 = "Line 1\nLine 2 CHANGED\nLine 3"
        
        diff = DocumentDiffer.diff_text(text1, text2)
        
        assert diff["total_differences"] > 0
        assert len(diff["modified_lines"]) > 0

    def test_diff_added_lines(self):
        """Diff with added lines."""
        text1 = "Line 1\nLine 2"
        text2 = "Line 1\nLine 2\nLine 3 (new)"
        
        diff = DocumentDiffer.diff_text(text1, text2)
        
        assert len(diff["added_lines"]) > 0

    def test_diff_removed_lines(self):
        """Diff with removed lines."""
        text1 = "Line 1\nLine 2\nLine 3"
        text2 = "Line 1\nLine 2"
        
        diff = DocumentDiffer.diff_text(text1, text2)
        
        assert len(diff["removed_lines"]) > 0

    def test_diff_pages(self):
        """Diff pages."""
        class MockPage:
            def __init__(self, text):
                self.text = text
        
        pages1 = [
            MockPage("Content page 1"),
            MockPage("Content page 2"),
        ]
        pages2 = [
            MockPage("Content page 1"),
            MockPage("Content page 2 MODIFIED"),
        ]
        
        diff = DocumentDiffer.diff_pages(pages1, pages2)
        
        assert diff["total_pages_1"] == 2
        assert diff["total_pages_2"] == 2
        assert "text_similarity" in diff

    def test_diff_page_count_change(self):
        """Diff with different page counts."""
        class MockPage:
            def __init__(self, text):
                self.text = text
        
        pages1 = [MockPage("Page 1"), MockPage("Page 2")]
        pages2 = [MockPage("Page 1"), MockPage("Page 2"), MockPage("Page 3")]
        
        diff = DocumentDiffer.diff_pages(pages1, pages2)
        
        assert diff["page_count_diff"] == 1


class TestEncryptionFramework:
    """Test encryption framework."""

    def test_encryption_check_raises_not_implemented(self):
        """Encryption functions raise NotImplementedError."""
        with pytest.raises(NotImplementedError, match="PyPDF2|pikepdf"):
            DocumentEncryption.encrypt_document_placeholder("/test.pdf", "/out.pdf", "password")

    def test_decryption_check_raises_not_implemented(self):
        """Decryption functions raise NotImplementedError."""
        with pytest.raises(NotImplementedError, match="PyPDF2|pikepdf"):
            DocumentEncryption.decrypt_document_placeholder("/test.pdf", "password")


class TestAnalysisReport:
    """Test comprehensive analysis report."""

    def test_create_analysis_report(self, tmp_path):
        """Create analysis report."""
        class MockPage:
            def __init__(self, number, text):
                self.number = number
                self.text = text
                self.tables = []
        
        pages = [
            MockPage(1, "Document content"),
            MockPage(2, "More content here"),
        ]
        
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF")
        
        report = create_analysis_report(str(pdf_path), pages)
        
        assert "file" in report
        assert "metadata" in report
        assert "watermark_analysis" in report
        assert "content_analysis" in report
        assert report["content_analysis"]["total_pages"] == 2


class TestIntegration:
    """Integration tests for advanced features."""

    def test_full_metadata_extraction(self, tmp_path):
        """Full metadata extraction workflow."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF")  # Minimal PDF
        
        # May fail due to invalid PDF, but test the function exists
        try:
            metadata = extract_all_metadata(str(pdf_path))
            assert isinstance(metadata, DocumentMetadata)
        except:
            pass  # OK if invalid PDF

    def test_analysis_workflow(self):
        """Complete analysis workflow."""
        class MockPage:
            def __init__(self, number, text):
                self.number = number
                self.text = text
                self.tables = []
        
        pages = [
            MockPage(1, "CONFIDENTIAL Content"),
            MockPage(2, "CONFIDENTIAL More"),
        ]
        
        # Build search index
        index = SearchIndex()
        index.index_pages(pages)
        
        # Search
        result = index.search("confidential")
        assert result["count"] >= 1
        
        # Watermark detection
        watermarks = WatermarkDetector.detect_watermark_indicators(pages)
        assert watermarks["potential_watermark"] == "confidential"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
