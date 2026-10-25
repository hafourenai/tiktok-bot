"""Data models for News Skill."""
from dataclasses import dataclass
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
class ArticleSummary:
    """Cached summary for article."""
    article_id: int
    summary: str
    summary_origin: str  # 'llm_full_text', 'llm_excerpt', 'source_excerpt'
    summary_model: str
    summary_created_at: datetime


@dataclass
class NewsResult:
    """Result of news fetch/process."""
    articles: list[Article]
    summaries: dict[str, str]  # canonical_url -> summary text
    error: Optional[str] = None
    cached: bool = False
    fetch_time: Optional[datetime] = None
