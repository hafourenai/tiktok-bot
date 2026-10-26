"""Data models for News Skill."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    """Single news article."""
    source_id: str
    category: str
    title: str
    canonical_url: str
    published_at_utc: datetime
    fetched_at_utc: datetime
    excerpt: str
    body: Optional[str] = None
    fingerprint: Optional[str] = None


@dataclass
class NewsResult:
    """Result of news fetch/process."""
    articles: list[Article]
    summaries: dict[str, str]  # canonical_url -> summary text
    summary_origins: dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    cached: bool = False
    fetch_time: Optional[datetime] = None
