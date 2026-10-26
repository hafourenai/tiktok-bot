"""News service orchestration."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.news.extractive import deterministic_summary
from src.news.extractor import get_article_content
from src.news.fetcher import (
    fetch_multiple_feeds,
    deduplicate_articles,
    sort_and_filter_articles,
)
from src.news.models import NewsResult
from src.news.sources import DEFAULT_FEEDS, get_feeds_for_category
from src.news.storage import NewsStorage
from src.news.summarizer import LLMSummarizer

logger = logging.getLogger(__name__)
EXTRACTIVE_VERSION = "extractive-v1"


class NewsService:
    """Main news service."""
    
    def __init__(
        self,
        db_path: str,
        llm_base_url: str,
        llm_model: str,
        llm_temperature: float = 0.2,
        llm_max_tokens: int = 120,
        llm_timeout: int = 45,
        http_timeout: int = 12,
        max_articles: int = 5,
        cache_ttl_seconds: int = 180,
        lookback_hours: int = 48,
        extract_timeout: int = 15,
        summary_mode: str = "auto",
        extractive_max_sentences: int = 2,
        extractive_max_words: int = 60,
        llm_health_timeout: float = 2.0,
        llm_cooldown_seconds: int = 300,
        llm_context_tokens: int = 1024,
        llm_concurrency: int = 1,
    ):
        self.storage = NewsStorage(db_path)
        self.summarizer = LLMSummarizer(
            base_url=llm_base_url,
            model=llm_model,
            temperature=llm_temperature,
            max_tokens=llm_max_tokens,
            timeout=llm_timeout,
            health_timeout=llm_health_timeout,
            cooldown_seconds=llm_cooldown_seconds,
            context_tokens=llm_context_tokens,
        )
        
        self.http_timeout = http_timeout
        self.max_articles = max_articles
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.lookback_hours = lookback_hours
        self.extract_timeout = extract_timeout
        self.summary_mode = summary_mode
        self.extractive_max_sentences = extractive_max_sentences
        self.extractive_max_words = extractive_max_words
        
        # Track fetch time per category for caching
        self._last_fetch: dict[str, datetime] = {}
        self._last_result: dict[str, NewsResult] = {}
        
        # Semaphore to limit concurrent LLM requests
        self._llm_semaphore = asyncio.Semaphore(max(1, llm_concurrency))

    def _usable_cached_summary(self, cached: tuple[str, str, str] | None) -> bool:
        if not cached:
            return False
        _, origin, model = cached
        if origin in {"publisher_summary", "extractive"}:
            return model == EXTRACTIVE_VERSION
        if origin in {"llm_full_text", "llm_excerpt"}:
            return self.summary_mode != "extractive" and model == self.summarizer.cache_model
        return False
    
    async def fetch_news(self, category: Optional[str] = None) -> NewsResult:
        """
        Fetch and process news for category.
        
        Returns NewsResult with articles and summaries or error.
        """
        try:
            # Determine which feeds to use
            if category:
                feeds = get_feeds_for_category(category)
                if not feeds:
                    return NewsResult(
                        articles=[],
                        summaries={},
                        error=f"Unknown category: {category}",
                    )
            else:
                feeds = DEFAULT_FEEDS
            
            # Check cache
            cache_key = category or "all"
            if cache_key in self._last_fetch:
                time_since_fetch = datetime.now(timezone.utc) - self._last_fetch[cache_key]
                if time_since_fetch < self.cache_ttl:
                    result = self._last_result.get(cache_key)
                    if result:
                        result.cached = True
                        result.fetch_time = self._last_fetch[cache_key]
                        logger.info("Using cached result for %s", cache_key or "all")
                        return result
            
            # Fetch feeds
            logger.info("Fetching feeds for %s...", category or "all")
            articles, feed_errors = await fetch_multiple_feeds(
                feeds,
                timeout=self.http_timeout,
            )
            
            if not articles:
                error_msg = "Failed to fetch news: " + "; ".join(feed_errors.values()) if feed_errors else "No articles available"
                return NewsResult(
                    articles=[],
                    summaries={},
                    error=error_msg,
                )
            
            # Deduplicate and sort
            articles = deduplicate_articles(articles)
            articles = sort_and_filter_articles(
                articles,
                max_articles=self.max_articles,
                lookback_hours=self.lookback_hours,
            )
            
            # Store and get IDs
            url_to_id = self.storage.insert_articles(articles)
            
            # Summarize articles
            summaries: dict[str, str] = {}
            summary_origins: dict[str, str] = {}
            llm_available = (
                self.summary_mode in {"auto", "llm"}
                and await self.summarizer.is_available()
            )
            for article in articles:
                article_id = url_to_id.get(article.canonical_url)

                # Check if summary already cached
                cached = self.storage.get_summary(article_id) if article_id else None
                if self._usable_cached_summary(cached):
                    summaries[article.canonical_url] = cached[0]
                    summary_origins[article.canonical_url] = cached[1]
                    logger.info("Using cached summary for %s", article.title[:50])
                    continue

                content = ""
                content_origin = "excerpt"
                summary_text = None
                summary_origin = ""
                error = "LLM unavailable"

                if llm_available:
                    content, content_origin = await get_article_content(
                        article.canonical_url,
                        article.excerpt,
                        timeout=self.extract_timeout,
                    )
                    async with self._llm_semaphore:
                        summary_text, error = await self.summarizer.summarize(
                            content,
                            article.title,
                        )
                    if summary_text:
                        summary_origin = f"llm_{content_origin}"
                    if error in {
                        "LLM server unreachable",
                        "LLM request timeout",
                        "LLM rate limited",
                    }:
                        llm_available = False
                        logger.warning("Disabling LLM for this request: %s", error)

                if not summary_text:
                    # Publisher RSS descriptions are usually already concise.
                    # Only fetch/extract HTML when the feed provides no useful
                    # description and LLM did not already obtain article text.
                    summary_text, summary_origin = deterministic_summary(
                        article.excerpt,
                        content,
                        article.title,
                        max_sentences=self.extractive_max_sentences,
                        max_words=self.extractive_max_words,
                    )
                    if summary_origin == "source_excerpt" and not content:
                        content, _ = await get_article_content(
                            article.canonical_url,
                            article.excerpt,
                            timeout=self.extract_timeout,
                        )
                        summary_text, summary_origin = deterministic_summary(
                            article.excerpt,
                            content,
                            article.title,
                            max_sentences=self.extractive_max_sentences,
                            max_words=self.extractive_max_words,
                        )
                    logger.info(
                        "Using %s for %s (%s)",
                        summary_origin,
                        article.title[:50],
                        error,
                    )

                summary_text = summary_text or article.excerpt or "Ringkasan belum tersedia."
                summary_origin = summary_origin or "source_excerpt"
                summaries[article.canonical_url] = summary_text
                summary_origins[article.canonical_url] = summary_origin

                if article_id and summary_origin != "source_excerpt":
                    model_version = (
                        self.summarizer.cache_model
                        if summary_origin.startswith("llm_")
                        else EXTRACTIVE_VERSION
                    )
                    self.storage.insert_summary(
                        article_id,
                        summary_text,
                        summary_origin,
                        model_version,
                    )
            
            # Cleanup old records
            self.storage.cleanup_old_records()
            
            # Cache result
            result = NewsResult(
                articles=articles,
                summaries=summaries,
                summary_origins=summary_origins,
                error=None if summaries else "No summaries generated",
                cached=False,
                fetch_time=datetime.now(timezone.utc),
            )
            self._last_fetch[cache_key] = datetime.now(timezone.utc)
            self._last_result[cache_key] = result
            
            return result
        except Exception as e:
            logger.exception("News fetch error")
            return NewsResult(
                articles=[],
                summaries={},
                error=f"Service error: {type(e).__name__}",
            )
