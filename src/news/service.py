"""News service orchestration."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.news.extractor import get_article_content
from src.news.fetcher import (
    fetch_multiple_feeds,
    deduplicate_articles,
    sort_and_filter_articles,
)
from src.news.models import Article, NewsResult
from src.news.sources import get_feeds_for_category
from src.news.storage import NewsStorage
from src.news.summarizer import LLMSummarizer

logger = logging.getLogger(__name__)


class NewsService:
    """Main news service."""
    
    def __init__(
        self,
        db_path: str,
        llm_base_url: str,
        llm_model: str,
        llm_temperature: float = 0.2,
        llm_max_tokens: int = 256,
        llm_timeout: int = 45,
        http_timeout: int = 12,
        max_articles: int = 5,
        cache_ttl_seconds: int = 180,
        lookback_hours: int = 48,
        extract_timeout: int = 15,
    ):
        self.storage = NewsStorage(db_path)
        self.summarizer = LLMSummarizer(
            base_url=llm_base_url,
            model=llm_model,
            temperature=llm_temperature,
            max_tokens=llm_max_tokens,
            timeout=llm_timeout,
        )
        
        self.http_timeout = http_timeout
        self.max_articles = max_articles
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.lookback_hours = lookback_hours
        self.extract_timeout = extract_timeout
        
        # Track fetch time per category for caching
        self._last_fetch: dict[str, datetime] = {}
        self._last_result: dict[str, NewsResult] = {}
        
        # Semaphore to limit concurrent LLM requests
        self._llm_semaphore = asyncio.Semaphore(1)
    
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
                # No specific category: fetch mix of recent from all
                from src.news.sources import ALL_FEEDS
                feeds = ALL_FEEDS
            
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
            summaries = {}
            for article in articles:
                article_id = url_to_id.get(article.canonical_url)
                if not article_id:
                    continue
                
                # Check if summary already cached
                cached = self.storage.get_summary(article_id)
                if cached:
                    summaries[article.canonical_url] = cached[0]
                    logger.info("Using cached summary for %s", article.title[:50])
                    continue
                
                # Extract text
                content, origin = await get_article_content(
                    article.canonical_url,
                    article.excerpt,
                    timeout=self.extract_timeout,
                )
                
                # Summarize with LLM
                async with self._llm_semaphore:
                    summary_text, error = await self.summarizer.summarize(
                        content,
                        article.title,
                    )
                
                if summary_text:
                    summaries[article.canonical_url] = summary_text
                    self.storage.insert_summary(
                        article_id,
                        summary_text,
                        f"llm_{origin}",
                        self.summarizer.model,
                    )
                    logger.info("Summarized: %s", article.title[:50])
                else:
                    # Fallback to excerpt
                    summaries[article.canonical_url] = article.excerpt
                    self.storage.insert_summary(
                        article_id,
                        article.excerpt,
                        "source_excerpt",
                        "fallback",
                    )
                    logger.info("Fallback to excerpt: %s (%s)", article.title[:50], error)
            
            # Cleanup old records
            self.storage.cleanup_old_records()
            
            # Cache result
            result = NewsResult(
                articles=articles,
                summaries=summaries,
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
