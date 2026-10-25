"""Unit tests for News Skill."""
import asyncio
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set environment variables before importing config
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("ALLOWED_TELEGRAM_USER_ID", "123")
os.environ.setdefault("NEWS_ENABLED", "true")


def test_article_model():
    """Test Article dataclass."""
    from src.news.models import Article
    
    article = Article(
        source_id="test_source",
        category="nasional",
        title="Test Article",
        canonical_url="https://example.com/article",
        published_at_utc=datetime.now(timezone.utc),
        fetched_at_utc=datetime.now(timezone.utc),
        excerpt="Test excerpt",
    )
    
    assert article.source_id == "test_source"
    assert article.title == "Test Article"
    assert article.category == "nasional"


def test_feed_config():
    """Test FeedConfig."""
    from src.news.sources import FeedConfig
    
    feed = FeedConfig(
        source_id="test",
        name="Test Feed",
        url="https://example.com/rss",
        category="nasional",
    )
    
    assert feed.source_id == "test"
    assert feed.category == "nasional"


def test_valid_categories():
    """Test category validation."""
    from src.news.sources import get_all_categories, is_valid_category
    
    cats = get_all_categories()
    assert "nasional" in cats
    assert "internasional" in cats
    assert "teknologi" in cats
    
    assert is_valid_category("nasional")
    assert is_valid_category("INTERNASIONAL")
    assert not is_valid_category("invalid_category")


def test_fingerprint_deduplication():
    """Test article fingerprinting."""
    from src.news.fetcher import fingerprint_article, deduplicate_articles
    from src.news.models import Article
    
    now = datetime.now(timezone.utc)
    
    # Create two articles with same title/URL
    article1 = Article(
        source_id="source1",
        category="nasional",
        title="Same Title",
        canonical_url="https://example.com/article",
        published_at_utc=now,
        fetched_at_utc=now,
        excerpt="",
        fingerprint=fingerprint_article("Same Title", "https://example.com/article"),
    )
    
    article2 = Article(
        source_id="source2",
        category="nasional",
        title="Same Title",
        canonical_url="https://example.com/article",
        published_at_utc=now,
        fetched_at_utc=now,
        excerpt="",
        fingerprint=fingerprint_article("Same Title", "https://example.com/article"),
    )
    
    # Different article
    article3 = Article(
        source_id="source3",
        category="nasional",
        title="Different Title",
        canonical_url="https://example.com/other",
        published_at_utc=now,
        fetched_at_utc=now,
        excerpt="",
        fingerprint=fingerprint_article("Different Title", "https://example.com/other"),
    )
    
    articles = [article1, article2, article3]
    unique = deduplicate_articles(articles)
    
    assert len(unique) == 2
    assert unique[0].canonical_url == "https://example.com/article"
    assert unique[1].canonical_url == "https://example.com/other"


def test_feed_html_is_converted_to_plain_text():
    """RSS markup must never be shown as literal HTML in Telegram."""
    from src.news.fetcher import clean_feed_text

    value = '<p>Berita <strong>penting</strong>&nbsp;hari ini.</p>'
    assert clean_feed_text(value) == "Berita penting hari ini."


def test_storage_initialization():
    """Test SQLite storage initialization."""
    from src.news.storage import NewsStorage
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        storage = NewsStorage(db_path)
        
        # Verify tables exist
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            assert "articles" in tables
            assert "summaries" in tables
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_storage_insert_and_retrieve():
    """Test inserting and retrieving articles."""
    from src.news.models import Article
    from src.news.storage import NewsStorage
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        storage = NewsStorage(db_path)
        now = datetime.now(timezone.utc)
        
        article = Article(
            source_id="test",
            category="nasional",
            title="Test",
            canonical_url="https://example.com",
            published_at_utc=now,
            fetched_at_utc=now,
            excerpt="Test excerpt",
            fingerprint="abc123",
        )
        
        url_to_id = storage.insert_articles([article])
        assert "https://example.com" in url_to_id
        
        # Insert summary
        article_id = url_to_id["https://example.com"]
        result = storage.insert_summary(
            article_id,
            "Test summary",
            "llm_full_text",
            "test-model",
        )
        assert result is True
        
        # Retrieve summary
        summary = storage.get_summary(article_id)
        assert summary is not None
        assert summary[0] == "Test summary"
        assert summary[1] == "llm_full_text"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_llm_summarizer_prompt():
    """Test LLM summarizer creates proper prompt."""
    from src.news.summarizer import LLMSummarizer
    
    summarizer = LLMSummarizer(
        base_url="http://localhost:8080",
        model="test-model",
    )
    
    # Test prompt construction (without actual API call)
    article_text = "Test article content"
    article_title = "Test Title"
    
    # Mock the httpx client
    with patch("src.news.summarizer.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test summary"}}]
        }
        mock_client.post.return_value = mock_response
        
        result, error = await summarizer.summarize(article_text, article_title)
        
        assert result == "Test summary"
        assert error is None
        
        # Verify the prompt was constructed correctly
        call_args = mock_client.post.call_args
        json_data = call_args.kwargs["json"]
        messages = json_data["messages"]
        prompt = messages[0]["content"]
        
        # Verify prompt contains safety guidelines
        assert "Bahasa Indonesia" in prompt
        assert "ATURAN" in prompt
        assert article_title in prompt


@pytest.mark.asyncio
async def test_url_security_validation():
    """Test URL security checks."""
    from src.news.security import is_safe_url
    
    # Valid HTTPS URL to allowed domain
    is_safe, reason = await is_safe_url("https://www.antaranews.com/article")
    assert is_safe is True
    
    # Non-HTTPS URL
    is_safe, reason = await is_safe_url("http://www.antaranews.com/article")
    assert is_safe is False
    assert "HTTPS" in reason
    
    # No hostname
    is_safe, reason = await is_safe_url("https://")
    assert is_safe is False


def test_message_splitting():
    """Test Telegram message splitting."""
    from src.news.handlers import split_message
    
    # Short message
    short = "Short message"
    split = split_message(short)
    assert len(split) == 1
    assert split[0] == short
    
    # Long message that exceeds limit
    long_msg = "A" * 5000
    split = split_message(long_msg)
    assert len(split) > 1
    
    # Verify each part is within limit
    for part in split:
        assert len(part) <= 4096


def test_news_skill_integration():
    """Test News Skill can be imported and initialized."""
    try:
        from src.news.service import NewsService
        from src.news.handlers import berita_command
        from src.news.sources import get_all_categories
        
        assert callable(berita_command)
        assert len(get_all_categories()) > 0
        
        # Should be able to instantiate service
        service = NewsService(
            db_path=":memory:",
            llm_base_url="http://127.0.0.1:8080",
            llm_model="test-model",
        )
        assert service is not None
    except Exception as e:
        pytest.fail(f"News Skill import failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
