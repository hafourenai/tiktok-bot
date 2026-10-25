"""Feed registry and source configuration."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FeedConfig:
    """Single RSS feed configuration."""
    source_id: str
    name: str
    url: str
    category: str
    language: str = "id"


# ANTARA News feeds — Indonesian sources
ANTARA_FEEDS = [
    FeedConfig("antara_terkini", "ANTARA Terkini", "https://www.antaranews.com/rss/terkini.xml", "nasional"),
    FeedConfig("antara_politik", "ANTARA Politik", "https://www.antaranews.com/rss/politik.xml", "politik"),
    FeedConfig("antara_ekonomi", "ANTARA Ekonomi", "https://www.antaranews.com/rss/ekonomi.xml", "ekonomi"),
    FeedConfig("antara_teknologi", "ANTARA Teknologi", "https://www.antaranews.com/rss/tekno.xml", "teknologi"),
    FeedConfig("antara_olahraga", "ANTARA Olahraga", "https://www.antaranews.com/rss/olahraga.xml", "olahraga"),
    FeedConfig("antara_dunia", "ANTARA Dunia", "https://www.antaranews.com/rss/dunia.xml", "internasional"),
]

# The Guardian feeds — International sources
GUARDIAN_FEEDS = [
    FeedConfig("guardian_world", "The Guardian World", "https://www.theguardian.com/world/rss", "internasional"),
    FeedConfig("guardian_tech", "The Guardian Technology", "https://www.theguardian.com/technology/rss", "teknologi"),
    FeedConfig("guardian_business", "The Guardian Business", "https://www.theguardian.com/business/rss", "ekonomi"),
]

# All available feeds (allowlist)
ALL_FEEDS = ANTARA_FEEDS + GUARDIAN_FEEDS

# Category to feed mapping
CATEGORY_FEEDS = {
    "nasional": [f for f in ALL_FEEDS if f.category == "nasional"],
    "internasional": [f for f in ALL_FEEDS if f.category == "internasional"],
    "teknologi": [f for f in ALL_FEEDS if f.category == "teknologi"],
    "ekonomi": [f for f in ALL_FEEDS if f.category == "ekonomi"],
    "politik": [f for f in ALL_FEEDS if f.category == "politik"],
    "olahraga": [f for f in ALL_FEEDS if f.category == "olahraga"],
}

# Allowed publisher domains for full-text extraction
ALLOWED_ARTICLE_DOMAINS = {
    "www.antaranews.com",
    "antaranews.com",
    "www.theguardian.com",
    "theguardian.com",
}


def get_feeds_for_category(category: str) -> list[FeedConfig]:
    """Get all feeds for a given category."""
    category_lower = category.lower().strip()
    return CATEGORY_FEEDS.get(category_lower, [])


def is_valid_category(category: str) -> bool:
    """Check if category exists."""
    return category.lower().strip() in CATEGORY_FEEDS


def get_all_categories() -> list[str]:
    """Get list of all valid categories."""
    return sorted(CATEGORY_FEEDS.keys())
