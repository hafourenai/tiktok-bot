"""Text styling and metadata extraction.

Preserves and extracts:
- Text formatting (bold, italic, underline, strikethrough)
- Font information (name, size, family)
- Text colors and backgrounds
- Language detection
- Text direction (LTR/RTL)
- Hyperlink information
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import re


class TextDirection(Enum):
    """Text reading direction."""
    LTR = "ltr"  # Left-to-right
    RTL = "rtl"  # Right-to-left
    MIXED = "mixed"


class TextStyle(Enum):
    """Text styling attributes."""
    NORMAL = "normal"
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    SUPERSCRIPT = "superscript"
    SUBSCRIPT = "subscript"


@dataclass
class FontInfo:
    """Font metadata."""
    
    __slots__ = ("name", "size", "family", "weight", "style", "color", "background")
    
    name: str  # e.g., "Arial", "Times New Roman"
    size: float  # Font size in points
    family: str  # "serif", "sans-serif", "monospace", "fantasy", "cursive"
    weight: int  # 100-900, default 400 (normal), 700 (bold)
    style: str  # "normal", "italic", "oblique"
    color: Optional[str]  # Hex color, e.g., "#FF0000"
    background: Optional[str]  # Background color

    def to_html_style(self) -> str:
        """Convert to HTML inline style."""
        styles = []
        styles.append(f"font-family: '{self.name}', {self.family}")
        styles.append(f"font-size: {self.size}pt")
        styles.append(f"font-weight: {self.weight}")
        styles.append(f"font-style: {self.style}")
        if self.color:
            styles.append(f"color: {self.color}")
        if self.background:
            styles.append(f"background-color: {self.background}")
        return "; ".join(styles)

    def __repr__(self):
        return f"<FontInfo {self.name} {self.size}pt weight={self.weight}>"


@dataclass
class StyledText:
    """Text with formatting."""
    
    __slots__ = ("text", "styles", "font", "direction", "language", "hyperlink", "metadata")
    
    text: str
    styles: set  # Set of TextStyle enums
    font: FontInfo
    direction: TextDirection
    language: str  # ISO 639-1 code, e.g., "en", "id", "es"
    hyperlink: Optional[str]  # URL if hyperlinked
    metadata: Dict  # Additional metadata

    def has_style(self, style: TextStyle) -> bool:
        """Check if text has a specific style."""
        return style in self.styles

    def to_markdown(self) -> str:
        """Convert to Markdown with formatting."""
        result = self.text
        
        if TextStyle.BOLD in self.styles:
            result = f"**{result}**"
        if TextStyle.ITALIC in self.styles:
            result = f"*{result}*"
        if TextStyle.STRIKETHROUGH in self.styles:
            result = f"~~{result}~~"
        if TextStyle.UNDERLINE in self.styles:
            result = f"<u>{result}</u>"
        
        if self.hyperlink:
            result = f"[{result}]({self.hyperlink})"
        
        return result

    def to_html(self) -> str:
        """Convert to HTML with formatting."""
        result = self.text
        
        tags = []
        if TextStyle.BOLD in self.styles:
            tags.append(("b", "b"))
        if TextStyle.ITALIC in self.styles:
            tags.append(("i", "i"))
        if TextStyle.UNDERLINE in self.styles:
            tags.append(("u", "u"))
        if TextStyle.STRIKETHROUGH in self.styles:
            tags.append(("s", "s"))
        if TextStyle.SUPERSCRIPT in self.styles:
            tags.append(("sup", "sup"))
        if TextStyle.SUBSCRIPT in self.styles:
            tags.append(("sub", "sub"))
        
        # Wrap with tags
        for open_tag, close_tag in tags:
            result = f"<{open_tag}>{result}</{close_tag}>"
        
        # Add font styling
        span_style = self.font.to_html_style()
        result = f'<span style="{span_style}">{result}</span>'
        
        # Hyperlink
        if self.hyperlink:
            result = f'<a href="{self.hyperlink}">{result}</a>'
        
        return result

    def __repr__(self):
        style_str = ",".join(s.value for s in self.styles) if self.styles else "normal"
        return f"<StyledText '{self.text[:20]}' {style_str} {self.language}>"


class TextAnalyzer:
    """Analyze and extract text styling."""

    # Common RTL languages
    RTL_LANGUAGES = {"ar", "he", "fa", "ur", "yi", "ji", "iw", "ku", "ps", "sd"}
    
    # Language detection patterns (simple heuristic)
    LANGUAGE_PATTERNS = {
        "id": r"[àáâãäåèéêëìíîïòóôõöùúûüýþÿ]|kata|yang|dengan",  # Indonesian
        "en": r"[a-z]{3,}",  # English (basic)
        "es": r"[àáâãäåèéêëìíîïòóôõöùúûüýþÿ]|que|para|con",  # Spanish
        "fr": r"[àâäéèêëïîôöœæüç]|que|pour|avec",  # French
        "de": r"[àáâãäåèéêëìíîïòóôõöùúûüýþÿß]|und|der|mit",  # German
        "zh": r"[\u4e00-\u9fff]",  # Chinese characters
        "ja": r"[\u3040-\u309f\u30a0-\u30ff]",  # Japanese
        "ar": r"[\u0600-\u06ff]",  # Arabic
    }

    @staticmethod
    def detect_language(text: str) -> str:
        """Detect language from text."""
        text_lower = text.lower()
        
        for lang, pattern in TextAnalyzer.LANGUAGE_PATTERNS.items():
            if re.search(pattern, text):
                return lang
        
        return "en"  # Default to English

    @staticmethod
    def detect_direction(text: str, language: str = None) -> TextDirection:
        """Detect text direction (LTR/RTL)."""
        if language is None:
            language = TextAnalyzer.detect_language(text)
        
        if language in TextAnalyzer.RTL_LANGUAGES:
            return TextDirection.RTL
        
        # Check for RTL characters
        rtl_chars = sum(1 for c in text if ord(c) >= 0x0600 and ord(c) <= 0x06ff)
        ltr_chars = sum(1 for c in text if c.isalpha() and ord(c) < 0x0600)
        
        if rtl_chars > ltr_chars:
            return TextDirection.RTL
        
        return TextDirection.LTR

    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract URLs from text."""
        url_pattern = r"https?://[^\s]+"
        return re.findall(url_pattern, text)

    @staticmethod
    def create_styled_text(
        text: str,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        font_name: str = "Arial",
        font_size: float = 12.0,
        color: Optional[str] = None,
        language: Optional[str] = None,
        hyperlink: Optional[str] = None,
    ) -> StyledText:
        """Create StyledText object."""
        
        styles = set()
        if bold:
            styles.add(TextStyle.BOLD)
        if italic:
            styles.add(TextStyle.ITALIC)
        if underline:
            styles.add(TextStyle.UNDERLINE)
        if strikethrough:
            styles.add(TextStyle.STRIKETHROUGH)
        
        if language is None:
            language = TextAnalyzer.detect_language(text)
        
        direction = TextAnalyzer.detect_direction(text, language)
        
        font = FontInfo(
            name=font_name,
            size=font_size,
            family="sans-serif",
            weight=700 if bold else 400,
            style="italic" if italic else "normal",
            color=color,
            background=None
        )
        
        return StyledText(
            text=text,
            styles=styles,
            font=font,
            direction=direction,
            language=language,
            hyperlink=hyperlink,
            metadata={}
        )


class ParagraphWithStyling:
    """Paragraph containing styled text segments."""
    
    __slots__ = ("segments", "language", "direction", "alignment")
    
    def __init__(self, segments: List[StyledText] = None):
        self.segments = segments or []
        self._update_metadata()
        self.alignment = "left"  # "left", "center", "right", "justify"

    def _update_metadata(self):
        """Update paragraph-level metadata from segments."""
        if not self.segments:
            self.language = "en"
            self.direction = TextDirection.LTR
            return
        
        # Use first segment's language/direction
        self.language = self.segments[0].language
        self.direction = self.segments[0].direction

    def add_segment(self, segment: StyledText):
        """Add styled text segment."""
        self.segments.append(segment)
        self._update_metadata()

    def plain_text(self) -> str:
        """Get plain text (no formatting)."""
        return "".join(s.text for s in self.segments)

    def to_markdown(self) -> str:
        """Convert paragraph to Markdown."""
        return "".join(s.to_markdown() for s in self.segments)

    def to_html(self) -> str:
        """Convert paragraph to HTML."""
        content = "".join(s.to_html() for s in self.segments)
        align = f' style="text-align: {self.alignment}"' if self.alignment != "left" else ""
        direction = f' dir="{self.direction.value}"'
        return f"<p{align}{direction}>{content}</p>"

    def __repr__(self):
        return f"<Paragraph {len(self.segments)} segments {self.language}>"


def extract_styled_sections(pages: List) -> List[Dict]:
    """Extract styled text sections from pages."""
    sections = []
    
    for page in pages:
        page_sections = {
            "page_number": page.number,
            "text": page.text,
            "language": TextAnalyzer.detect_language(page.text),
            "direction": TextAnalyzer.detect_direction(page.text).value,
            "has_urls": bool(TextAnalyzer.extract_urls(page.text)),
            "urls": TextAnalyzer.extract_urls(page.text),
        }
        sections.append(page_sections)
    
    return sections


def create_rich_document(pages: List) -> Dict:
    """Create rich document with styling metadata."""
    document = {
        "metadata": {
            "total_pages": len(pages),
            "languages": set(),
            "has_rtl": False,
        },
        "sections": []
    }
    
    for page in pages:
        lang = TextAnalyzer.detect_language(page.text)
        direction = TextAnalyzer.detect_direction(page.text, lang)
        
        document["metadata"]["languages"].add(lang)
        if direction == TextDirection.RTL:
            document["metadata"]["has_rtl"] = True
        
        section = {
            "page": page.number,
            "language": lang,
            "direction": direction.value,
            "text": page.text,
            "tables": page.tables,
        }
        document["sections"].append(section)
    
    # Convert set to list for JSON serialization
    document["metadata"]["languages"] = list(document["metadata"]["languages"])
    
    return document


__all__ = [
    "TextDirection",
    "TextStyle",
    "FontInfo",
    "StyledText",
    "TextAnalyzer",
    "ParagraphWithStyling",
    "extract_styled_sections",
    "create_rich_document",
]
