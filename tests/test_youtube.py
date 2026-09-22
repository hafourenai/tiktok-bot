import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from downloader import download_youtube, cleanup_downloads
from config import DOWNLOAD_DIR

def test_youtube_url_validation():
    """Test YouTube URL regex validation."""
    from config import YOUTUBE_URL_RE
    
    valid_urls = [
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ&t=10s",
    ]
    
    invalid_urls = [
        "https://youtu.be/",
        "https://youtube.com/",
        "https://youtu.be/short",
        "https://tiktok.com/watch?v=dQw4w9WgXcQ",
    ]
    
    for url in valid_urls:
        assert YOUTUBE_URL_RE.search(url), f"Valid URL rejected: {url}"
    
    for url in invalid_urls:
        assert not YOUTUBE_URL_RE.search(url), f"Invalid URL accepted: {url}"
    
    print("✓ YouTube URL validation tests passed")


def test_tiktok_url_validation():
    """Test TikTok URL regex validation."""
    from config import TIKTOK_URL_RE
    
    valid_urls = [
        "https://tiktok.com/@user/video/1234567890",
        "https://www.tiktok.com/@user/video/1234567890",
        "https://vm.tiktok.com/ABC123/",
        "https://vt.tiktok.com/ABC123/",
    ]
    
    invalid_urls = [
        "https://youtube.com/watch?v=abc",
        "https://tiktok.com/@user",
        "https://vt.tiktok.com/",
    ]
    
    for url in valid_urls:
        assert TIKTOK_URL_RE.fullmatch(url), f"Valid TikTok URL rejected: {url}"
    
    for url in invalid_urls:
        assert not TIKTOK_URL_RE.fullmatch(url), f"Invalid TikTok URL accepted: {url}"
    
    print("✓ TikTok URL validation tests passed")


def test_config_imports():
    """Test that all config imports work correctly."""
    from config import (
        TELEGRAM_BOT_TOKEN,
        ALLOWED_USER_ID,
        DOWNLOAD_DIR,
        MAX_FILE_SIZE_BYTES,
        TIKTOK_URL_RE,
        YOUTUBE_URL_RE,
    )
    
    assert ALLOWED_USER_ID > 0, "ALLOWED_USER_ID must be positive"
    assert MAX_FILE_SIZE_BYTES > 0, "MAX_FILE_SIZE_BYTES must be positive"
    assert TIKTOK_URL_RE is not None, "TIKTOK_URL_RE must exist"
    assert YOUTUBE_URL_RE is not None, "YOUTUBE_URL_RE must exist"
    
    print("✓ Config import tests passed")


if __name__ == "__main__":
    test_youtube_url_validation()
    test_tiktok_url_validation()
    test_config_imports()
    print("\n✅ All tests passed")

