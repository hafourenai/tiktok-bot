"""Unit tests for News Skill."""
import asyncio
import os
import sqlite3
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


def test_storage_initialization(tmp_path):
    """Test SQLite storage initialization."""
    from src.news.storage import NewsStorage
    
    db_path = tmp_path / "news.db"
    storage = NewsStorage(db_path)

    # Verify tables exist
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "articles" in tables
        assert "summaries" in tables


def test_storage_insert_and_retrieve(tmp_path):
    """Test inserting and retrieving articles."""
    from src.news.models import Article
    from src.news.storage import NewsStorage
    
    db_path = tmp_path / "news.db"
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
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
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
        assert "/no_think" in prompt
        assert "30-60 kata" in prompt
        assert article_title in prompt


def test_publisher_summary_is_short_and_factual():
    from src.news.extractive import deterministic_summary

    excerpt = (
        "Pemerintah menunda kewajiban sertifikasi halal bagi UMKM hingga 2028. "
        "Kebijakan itu memberi waktu tambahan bagi pelaku usaha untuk memenuhi persyaratan."
    )
    summary, origin = deterministic_summary(excerpt, "", "Sertifikasi halal ditunda")

    assert origin == "publisher_summary"
    assert "hingga 2028" in summary
    assert len(summary.split()) <= 60


def test_truncated_publisher_excerpt_falls_back_to_body():
    from src.news.extractive import deterministic_summary

    summary, origin = deterministic_summary(
        "Pemerintah Kota Jakarta Timur menyalurkan bantuan ...",
        "Pemerintah Kota Jakarta Timur menyalurkan bantuan kebutuhan dasar kepada penyintas kebakaran di Rawamangun.",
        "Pemkot bantu penyintas kebakaran",
    )

    assert origin == "extractive"
    assert summary.endswith("Rawamangun.")


def test_low_context_teaser_is_prefixed_with_publisher_headline():
    from src.news.extractive import publisher_summary

    summary = publisher_summary(
        "Petugas pun ikut curiga karena jalan menuju lokasi sempit dan rusak.",
        "Mekanik di Tangerang Dikirimi Tagihan Pajak McLaren Rp137 Juta",
    )

    assert summary.startswith("Mekanik di Tangerang")
    assert "Petugas pun ikut curiga" in summary


def test_extractive_summary_uses_source_sentences():
    from src.news.extractive import deterministic_summary

    body = (
        "Baca juga: Informasi lainnya. "
        "Kabut asap pekat memaksa panitia membatalkan konser di Palembang. "
        "Bernadya dan Mahalini batal tampil demi kesehatan warga dan kru."
    )
    summary, origin = deterministic_summary("", body, "Konser Palembang batal")

    assert origin == "extractive"
    assert "Baca juga" not in summary
    assert "Bernadya" in summary


def test_default_feeds_only_use_indonesian_publishers():
    from src.news.sources import DEFAULT_FEEDS, get_feeds_for_category

    assert {feed.publisher for feed in DEFAULT_FEEDS} == {"ANTARA News", "CNN Indonesia"}
    assert {feed.publisher for feed in get_feeds_for_category("teknologi")} == {
        "ANTARA News", "CNN Indonesia"
    }
    assert "The Guardian" in {
        feed.publisher for feed in get_feeds_for_category("internasional")
    }


def test_article_selection_balances_publishers():
    from datetime import timedelta
    from src.news.fetcher import sort_and_filter_articles
    from src.news.models import Article

    now = datetime.now(timezone.utc)

    def article(source_id, index):
        return Article(
            source_id=source_id,
            category="nasional",
            title=f"Artikel {source_id} {index}",
            canonical_url=f"https://example.com/{source_id}/{index}",
            published_at_utc=now - timedelta(minutes=index),
            fetched_at_utc=now,
            excerpt="Isi berita yang cukup panjang untuk diuji.",
        )

    articles = [article("antara_terkini", i) for i in range(5)]
    articles += [article("cnn_nasional", i) for i in range(5)]
    selected = sort_and_filter_articles(articles, max_articles=5, max_per_publisher=2)

    assert len(selected) == 4
    assert sum(item.source_id.startswith("antara_") for item in selected) == 2
    assert sum(item.source_id.startswith("cnn_") for item in selected) == 2


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


def test_compact_article_format_has_no_date_or_internal_source_id():
    from src.news.handlers import format_article_message
    from src.news.models import Article

    now = datetime.now(timezone.utc)
    article = Article(
        source_id="cnn_nasional",
        category="nasional",
        title="Operasi Patuh Jaya Digelar 14 Hari",
        canonical_url="https://www.cnnindonesia.com/nasional/example",
        published_at_utc=now,
        fetched_at_utc=now,
        excerpt="Kapolda mewajibkan penindakan direkam menggunakan video.",
    )
    result = format_article_message(
        article,
        "Kapolda mewajibkan setiap penindakan direkam menggunakan video.",
        "publisher_summary",
        1,
    )

    assert "1. Operasi Patuh" in result
    assert "CNN Indonesia" in result
    assert "cnn_nasional" not in result
    assert "WIB" not in result


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
