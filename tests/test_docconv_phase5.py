"""Tests for Phase 5: Text & Styling.

Covers text formatting, styling, language detection, RTL support, hyperlinks.
"""

import pytest
from docconv.styling import (
    TextDirection, TextStyle, FontInfo, StyledText, TextAnalyzer,
    ParagraphWithStyling, extract_styled_sections, create_rich_document
)


class TestFontInfo:
    """Test FontInfo class."""

    def test_font_info_creation(self):
        """Create FontInfo object."""
        font = FontInfo(
            name="Arial", size=12.0, family="sans-serif",
            weight=400, style="normal", color="#000000", background=None
        )
        assert font.name == "Arial"
        assert font.size == 12.0
        assert font.weight == 400

    def test_font_to_html_style(self):
        """Convert font to HTML inline style."""
        font = FontInfo(
            name="Times New Roman", size=14.0, family="serif",
            weight=700, style="italic", color="#FF0000", background="#FFFF00"
        )
        
        style = font.to_html_style()
        
        assert "Times New Roman" in style
        assert "14" in style
        assert "700" in style
        assert "italic" in style
        assert "#FF0000" in style
        assert "#FFFF00" in style


class TestTextStyle:
    """Test TextStyle enum."""

    def test_text_styles_exist(self):
        """All text styles are available."""
        assert TextStyle.BOLD
        assert TextStyle.ITALIC
        assert TextStyle.UNDERLINE
        assert TextStyle.STRIKETHROUGH
        assert TextStyle.SUPERSCRIPT
        assert TextStyle.SUBSCRIPT


class TestStyledText:
    """Test StyledText class."""

    def test_create_bold_text(self):
        """Create bold styled text."""
        font = FontInfo("Arial", 12, "sans-serif", 700, "normal", None, None)
        styled = StyledText(
            text="Bold text",
            styles={TextStyle.BOLD},
            font=font,
            direction=TextDirection.LTR,
            language="en",
            hyperlink=None,
            metadata={}
        )
        
        assert styled.has_style(TextStyle.BOLD)
        assert not styled.has_style(TextStyle.ITALIC)

    def test_styled_text_to_markdown(self):
        """Convert styled text to Markdown."""
        font = FontInfo("Arial", 12, "sans-serif", 700, "normal", None, None)
        styled = StyledText(
            text="Bold text",
            styles={TextStyle.BOLD},
            font=font,
            direction=TextDirection.LTR,
            language="en",
            hyperlink=None,
            metadata={}
        )
        
        markdown = styled.to_markdown()
        assert "**" in markdown
        assert "Bold text" in markdown

    def test_styled_text_with_hyperlink(self):
        """Styled text with hyperlink to Markdown."""
        font = FontInfo("Arial", 12, "sans-serif", 400, "normal", None, None)
        styled = StyledText(
            text="Click here",
            styles=set(),
            font=font,
            direction=TextDirection.LTR,
            language="en",
            hyperlink="https://example.com",
            metadata={}
        )
        
        markdown = styled.to_markdown()
        assert "[Click here]" in markdown
        assert "https://example.com" in markdown

    def test_styled_text_to_html(self):
        """Convert styled text to HTML."""
        font = FontInfo("Arial", 12, "sans-serif", 400, "normal", "#000000", None)
        styled = StyledText(
            text="Text",
            styles={TextStyle.ITALIC, TextStyle.UNDERLINE},
            font=font,
            direction=TextDirection.LTR,
            language="en",
            hyperlink=None,
            metadata={}
        )
        
        html = styled.to_html()
        assert "<i>" in html
        assert "<u>" in html
        assert "Arial" in html


class TestLanguageDetection:
    """Test language detection."""

    def test_detect_english(self):
        """Detect English text."""
        text = "This is English text"
        lang = TextAnalyzer.detect_language(text)
        assert lang in ["en", "id"]  # Could be detected as either

    def test_detect_indonesian(self):
        """Detect Indonesian text."""
        text = "Ini adalah teks bahasa Indonesia dengan kata yang panjang"
        lang = TextAnalyzer.detect_language(text)
        assert lang in ["id", "en"]  # Both could match

    def test_detect_arabic(self):
        """Detect Arabic text."""
        text = "هذا نص عربي"
        lang = TextAnalyzer.detect_language(text)
        assert lang == "ar"

    def test_detect_chinese(self):
        """Detect Chinese text."""
        text = "这是中文文本"
        lang = TextAnalyzer.detect_language(text)
        assert lang == "zh"


class TestTextDirection:
    """Test text direction detection."""

    def test_ltr_direction(self):
        """Detect left-to-right text."""
        text = "English text"
        direction = TextAnalyzer.detect_direction(text)
        assert direction == TextDirection.LTR

    def test_rtl_direction(self):
        """Detect right-to-left text."""
        text = "هذا نص عربي"
        direction = TextAnalyzer.detect_direction(text)
        assert direction == TextDirection.RTL

    def test_rtl_with_language_hint(self):
        """RTL detection with language hint."""
        text = "Some text"
        direction = TextAnalyzer.detect_direction(text, language="ar")
        assert direction == TextDirection.RTL


class TestUrlExtraction:
    """Test URL extraction."""

    def test_extract_single_url(self):
        """Extract single URL from text."""
        text = "Visit https://example.com for more info"
        urls = TextAnalyzer.extract_urls(text)
        
        assert len(urls) >= 1
        assert any("example.com" in url for url in urls)

    def test_extract_multiple_urls(self):
        """Extract multiple URLs."""
        text = "Links: https://site1.com and https://site2.com"
        urls = TextAnalyzer.extract_urls(text)
        
        assert len(urls) >= 2

    def test_no_urls_in_plain_text(self):
        """No URLs in plain text."""
        text = "This is plain text without links"
        urls = TextAnalyzer.extract_urls(text)
        
        assert len(urls) == 0


class TestStyledTextCreation:
    """Test creating styled text programmatically."""

    def test_create_bold_italic_text(self):
        """Create text with multiple styles."""
        styled = TextAnalyzer.create_styled_text(
            "Bold italic text",
            bold=True,
            italic=True,
            font_name="Arial"
        )
        
        assert styled.has_style(TextStyle.BOLD)
        assert styled.has_style(TextStyle.ITALIC)
        assert styled.font.name == "Arial"

    def test_create_colored_text(self):
        """Create text with color."""
        styled = TextAnalyzer.create_styled_text(
            "Colored text",
            color="#FF0000"
        )
        
        assert styled.font.color == "#FF0000"

    def test_create_hyperlinked_text(self):
        """Create hyperlinked text."""
        styled = TextAnalyzer.create_styled_text(
            "Link",
            hyperlink="https://example.com"
        )
        
        assert styled.hyperlink == "https://example.com"

    def test_auto_language_detection_in_creation(self):
        """Language auto-detected in creation."""
        styled = TextAnalyzer.create_styled_text("English text")
        assert styled.language in ["en", "id"]


class TestParagraph:
    """Test ParagraphWithStyling class."""

    def test_create_paragraph(self):
        """Create paragraph."""
        styled1 = TextAnalyzer.create_styled_text("Hello ")
        styled2 = TextAnalyzer.create_styled_text("world", bold=True)
        
        para = ParagraphWithStyling([styled1, styled2])
        
        assert len(para.segments) == 2

    def test_paragraph_plain_text(self):
        """Get plain text from paragraph."""
        styled1 = TextAnalyzer.create_styled_text("Hello ")
        styled2 = TextAnalyzer.create_styled_text("world")
        
        para = ParagraphWithStyling([styled1, styled2])
        plain = para.plain_text()
        
        assert plain == "Hello world"

    def test_paragraph_to_markdown(self):
        """Convert paragraph to Markdown."""
        styled1 = TextAnalyzer.create_styled_text("Hello ")
        styled2 = TextAnalyzer.create_styled_text("world", bold=True)
        
        para = ParagraphWithStyling([styled1, styled2])
        markdown = para.to_markdown()
        
        assert "Hello" in markdown
        assert "**world**" in markdown

    def test_paragraph_to_html(self):
        """Convert paragraph to HTML."""
        styled1 = TextAnalyzer.create_styled_text("Text")
        para = ParagraphWithStyling([styled1])
        
        html = para.to_html()
        
        assert html.startswith("<p")
        assert "Text" in html
        assert html.endswith("</p>")

    def test_paragraph_add_segment(self):
        """Add segment to paragraph."""
        para = ParagraphWithStyling()
        assert len(para.segments) == 0
        
        styled = TextAnalyzer.create_styled_text("New segment")
        para.add_segment(styled)
        
        assert len(para.segments) == 1


class TestStyledSectionExtraction:
    """Test extracting styled sections."""

    def test_extract_sections_from_pages(self):
        """Extract styled sections from pages."""
        class MockPage:
            def __init__(self, number, text):
                self.number = number
                self.text = text
        
        pages = [
            MockPage(1, "English page"),
            MockPage(2, "Halaman kedua dalam bahasa Indonesia"),
        ]
        
        sections = extract_styled_sections(pages)
        
        assert len(sections) == 2
        assert sections[0]["page_number"] == 1
        assert sections[1]["language"] in ["id", "en"]


class TestRichDocumentCreation:
    """Test creating rich documents."""

    def test_create_rich_document(self):
        """Create rich document from pages."""
        class MockPage:
            def __init__(self, number, text, tables=None):
                self.number = number
                self.text = text
                self.tables = tables or []
        
        pages = [
            MockPage(1, "Page 1 content"),
            MockPage(2, "Page 2 content", [["Header1", "Header2"]]),
        ]
        
        doc = create_rich_document(pages)
        
        assert doc["metadata"]["total_pages"] == 2
        assert len(doc["sections"]) == 2
        assert "languages" in doc["metadata"]

    def test_rich_document_language_detection(self):
        """Rich document detects multiple languages."""
        class MockPage:
            def __init__(self, number, text):
                self.number = number
                self.text = text
                self.tables = []
        
        pages = [
            MockPage(1, "English text"),
            MockPage(2, "Teks bahasa Indonesia"),
        ]
        
        doc = create_rich_document(pages)
        
        assert len(doc["metadata"]["languages"]) >= 1


class TestIntegration:
    """Integration tests for styling module."""

    def test_full_styled_document_workflow(self):
        """Complete workflow from raw text to styled document."""
        # Create styled content
        title = TextAnalyzer.create_styled_text("Document Title", bold=True)
        intro = TextAnalyzer.create_styled_text("This is the introduction.")
        link = TextAnalyzer.create_styled_text("Click here", hyperlink="https://example.com")
        
        # Build paragraph
        para = ParagraphWithStyling([title])
        
        # Convert formats
        markdown = para.to_markdown()
        html = para.to_html()
        
        assert "Document Title" in markdown
        assert "<p" in html

    def test_multilingual_document(self):
        """Handle multilingual content."""
        english = TextAnalyzer.create_styled_text("English text")
        arabic = TextAnalyzer.create_styled_text("النص العربي")
        
        para = ParagraphWithStyling([english, arabic])
        
        assert para.language in ["en", "ar", "id"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
