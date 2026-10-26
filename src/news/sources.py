"""Static registry of approved publisher feeds."""
from dataclasses import dataclass


@dataclass
class FeedConfig:
    """Single RSS feed configuration."""
    source_id: str
    name: str
    url: str
    category: str
    language: str = "id"
    publisher: str = ""


# ANTARA News feeds — Indonesian sources
ANTARA_FEEDS = [
    FeedConfig("antara_terkini", "ANTARA Terkini", "https://www.antaranews.com/rss/terkini.xml", "nasional", publisher="ANTARA News"),
    FeedConfig("antara_politik", "ANTARA Politik", "https://www.antaranews.com/rss/politik.xml", "politik", publisher="ANTARA News"),
    FeedConfig("antara_ekonomi", "ANTARA Ekonomi", "https://www.antaranews.com/rss/ekonomi.xml", "ekonomi", publisher="ANTARA News"),
    FeedConfig("antara_teknologi", "ANTARA Teknologi", "https://www.antaranews.com/rss/tekno.xml", "teknologi", publisher="ANTARA News"),
    FeedConfig("antara_olahraga", "ANTARA Olahraga", "https://www.antaranews.com/rss/olahraga.xml", "olahraga", publisher="ANTARA News"),
    FeedConfig("antara_dunia", "ANTARA Dunia", "https://www.antaranews.com/rss/dunia.xml", "internasional", publisher="ANTARA News"),
]


# CNN Indonesia exposes these feeds through alternate RSS links on its site.
CNN_FEEDS = [
    FeedConfig("cnn_nasional", "CNN Indonesia Nasional", "https://www.cnnindonesia.com/nasional/rss", "nasional", publisher="CNN Indonesia"),
    FeedConfig("cnn_internasional", "CNN Indonesia Internasional", "https://www.cnnindonesia.com/internasional/rss", "internasional", publisher="CNN Indonesia"),
    FeedConfig("cnn_ekonomi", "CNN Indonesia Ekonomi", "https://www.cnnindonesia.com/ekonomi/rss", "ekonomi", publisher="CNN Indonesia"),
    FeedConfig("cnn_teknologi", "CNN Indonesia Teknologi", "https://www.cnnindonesia.com/teknologi/rss", "teknologi", publisher="CNN Indonesia"),
    FeedConfig("cnn_olahraga", "CNN Indonesia Olahraga", "https://www.cnnindonesia.com/olahraga/rss", "olahraga", publisher="CNN Indonesia"),
]

# The Guardian feeds — International sources
GUARDIAN_FEEDS = [
    FeedConfig("guardian_world", "The Guardian World", "https://www.theguardian.com/world/rss", "internasional", "en", "The Guardian"),
    FeedConfig("guardian_tech", "The Guardian Technology", "https://www.theguardian.com/technology/rss", "teknologi", "en", "The Guardian"),
    FeedConfig("guardian_business", "The Guardian Business", "https://www.theguardian.com/business/rss", "ekonomi", "en", "The Guardian"),
]

# All available feeds (allowlist)
ALL_FEEDS = ANTARA_FEEDS + CNN_FEEDS + GUARDIAN_FEEDS

# The default command intentionally stays Indonesian and balanced. Guardian is
# available through explicit categories, especially ``internasional``.
DEFAULT_FEEDS = [ANTARA_FEEDS[0], CNN_FEEDS[0]]

# Category to feed mapping
CATEGORY_FEEDS = {
    "nasional": [ANTARA_FEEDS[0], CNN_FEEDS[0]],
    "internasional": [ANTARA_FEEDS[5], CNN_FEEDS[1], GUARDIAN_FEEDS[0]],
    "teknologi": [ANTARA_FEEDS[3], CNN_FEEDS[3]],
    "ekonomi": [ANTARA_FEEDS[2], CNN_FEEDS[2]],
    "politik": [ANTARA_FEEDS[1]],
    "olahraga": [ANTARA_FEEDS[4], CNN_FEEDS[4]],
}

# Allowed publisher domains for full-text extraction
ALLOWED_ARTICLE_DOMAINS = {
    "www.antaranews.com",
    "antaranews.com",
    "www.theguardian.com",
    "theguardian.com",
    "www.cnnindonesia.com",
    "cnnindonesia.com",
}

SOURCE_PUBLISHERS = {feed.source_id: feed.publisher or feed.name for feed in ALL_FEEDS}


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


def publisher_for_source(source_id: str) -> str:
    """Return the public publisher name for an internal source ID."""
    return SOURCE_PUBLISHERS.get(source_id, source_id.replace("_", " ").title())
