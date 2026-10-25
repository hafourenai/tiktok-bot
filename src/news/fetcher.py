"""RSS fetching and parsing."""
import asyncio
import hashlib
import html
import logging
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse

import feedparser
import httpx

from src.news.models import Article
from src.news.sources import FeedConfig
from src.news.security import is_safe_url, is_safe_redirect

logger = logging.getLogger(__name__)

# Conservative defaults
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 10
DEFAULT_MAX_REDIRECTS = 3
DEFAULT_MAX_FEED_SIZE = 2 * 1024 * 1024  # 2 MB
DEFAULT_MAX_RETRIES = 2


class _HTMLTextExtractor(HTMLParser):
    """Collect visible text from a short RSS HTML fragment."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data)


def clean_feed_text(value: str, limit: int = 500) -> str:
    """Convert RSS HTML fragments/entities into normalized plain text."""
    if not value:
        return ""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(value)
        parser.close()
        text = " ".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def create_http_client(
    timeout: int = DEFAULT_READ_TIMEOUT,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> httpx.AsyncClient:
    """Create configured HTTP client."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout=timeout, connect=DEFAULT_CONNECT_TIMEOUT),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    )


def fingerprint_article(title: str, url: str) -> str:
    """Create fingerprint for deduplication."""
    content = f"{title}:{url}".lower().encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]


def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    parsed = urlparse(url)
    # Remove query params and fragments for canonical form
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def parse_rfc822_date(date_str: str) -> Optional[datetime]:
    """Parse RFC 822 date string."""
    if not date_str:
        return None
    try:
        # feedparser normalizes dates to time.struct_time
        # We need to convert back to datetime
        import email.utils
        parsed_tuple = email.utils.parsedate_to_datetime(date_str)
        return parsed_tuple
    except (TypeError, ValueError):
        return None


def extract_feed_article(entry: dict, feed_config: FeedConfig, fetched_at: datetime) -> Optional[Article]:
    """Extract article from feed entry."""
    try:
        # Title is required
        title = clean_feed_text(entry.get("title") or "", limit=300)
        if not title:
            return None
        
        # URL is required
        url = (entry.get("link") or "").strip()
        if not url or not url.startswith(("http://", "https://")):
            return None
        
        # Normalize URL
        canonical_url = normalize_url(url)
        
        # Published date
        published_at = None
        if entry.get("published"):
            published_at = parse_rfc822_date(entry.get("published"))
        elif entry.get("updated"):
            published_at = parse_rfc822_date(entry.get("updated"))
        
        if published_at is None:
            published_at = datetime.now(timezone.utc)
        elif published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        else:
            published_at = published_at.astimezone(timezone.utc)
        
        # Excerpt from summary
        excerpt = clean_feed_text(
            entry.get("summary") or entry.get("description") or "",
            limit=500,
        )
        
        # Fingerprint for deduplication
        fp = fingerprint_article(title, canonical_url)
        
        return Article(
            source_id=feed_config.source_id,
            category=feed_config.category,
            title=title,
            canonical_url=canonical_url,
            published_at_utc=published_at,
            fetched_at_utc=fetched_at,
            excerpt=excerpt,
            fingerprint=fp,
        )
    except Exception as e:
        logger.warning("Failed to extract article from entry: %s", e)
        return None


async def fetch_feed(
    feed_config: FeedConfig,
    client: httpx.AsyncClient,
    timeout: int = DEFAULT_READ_TIMEOUT,
) -> tuple[list[Article], Optional[str]]:
    """
    Fetch and parse single RSS feed.
    
    Returns: (articles, error_message)
    """
    try:
        # Validate feed URL
        is_safe, reason = await is_safe_url(feed_config.url)
        if not is_safe:
            return [], f"Feed URL unsafe: {reason}"
        
        # Fetch with retry
        response = None
        last_error = None
        for attempt in range(DEFAULT_MAX_RETRIES):
            try:
                response = await client.get(feed_config.url, follow_redirects=True)
                response.raise_for_status()
                break
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < DEFAULT_MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)  # Backoff: 1s, 2s, 4s
                    continue
        
        if response is None:
            return [], f"Failed to fetch feed: {last_error}"
        
        # Check size
        if len(response.content) > DEFAULT_MAX_FEED_SIZE:
            return [], f"Feed exceeds size limit ({len(response.content)} bytes)"
        
        # Parse RSS
        fetched_at = datetime.now(timezone.utc)
        parsed = feedparser.parse(response.content)
        
        if parsed.get("bozo"):
            logger.warning("Feed parse warning for %s: %s", feed_config.source_id, parsed.get("bozo_exception"))
        
        # Extract articles
        articles = []
        for entry in parsed.get("entries", []):
            article = extract_feed_article(entry, feed_config, fetched_at)
            if article:
                articles.append(article)
        
        if not articles:
            return [], "No articles found in feed"
        
        logger.info("Fetched %d articles from %s", len(articles), feed_config.source_id)
        return articles, None
    except Exception as e:
        logger.exception("Error fetching feed %s", feed_config.source_id)
        return [], f"Feed fetch error: {type(e).__name__}"


async def fetch_multiple_feeds(
    feeds: list[FeedConfig],
    timeout: int = DEFAULT_READ_TIMEOUT,
) -> tuple[list[Article], dict[str, str]]:
    """
    Fetch multiple feeds in parallel.
    
    Returns: (all_articles, feed_errors)
    """
    client = create_http_client(timeout=timeout)
    feed_errors = {}
    all_articles = []
    
    try:
        tasks = [fetch_feed(feed, client, timeout) for feed in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        for feed, (articles, error) in zip(feeds, results):
            if error:
                feed_errors[feed.source_id] = error
            else:
                all_articles.extend(articles)
    finally:
        await client.aclose()
    
    return all_articles, feed_errors


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    """Remove duplicate articles by URL and fingerprint."""
    seen_urls = set()
    seen_fps = set()
    unique = []
    
    for article in articles:
        if article.canonical_url in seen_urls:
            continue
        if article.fingerprint in seen_fps:
            continue
        seen_urls.add(article.canonical_url)
        seen_fps.add(article.fingerprint)
        unique.append(article)
    
    return unique


def sort_and_filter_articles(
    articles: list[Article],
    max_articles: int = 5,
    lookback_hours: int = 48,
) -> list[Article]:
    """
    Sort articles by recency and filter.
    - Prioritize articles ≤48 hours old
    - Remove future-dated articles
    """
    now = datetime.now(timezone.utc)
    cutoff_recent = datetime.fromtimestamp(now.timestamp() - lookback_hours * 3600, tz=timezone.utc)
    
    # Filter out invalid dates
    valid = []
    for article in articles:
        # Reject future dates
        if article.published_at_utc > now:
            logger.warning("Skipping future-dated article: %s", article.title[:50])
            continue
        valid.append(article)
    
    # Sort by date descending, with recent articles first
    valid.sort(key=lambda a: a.published_at_utc, reverse=True)
    
    # Take top N
    return valid[:max_articles]
