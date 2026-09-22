import os
import sys
from pathlib import Path

os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["ALLOWED_TELEGRAM_USER_ID"] = "123"
sys.path.insert(0, str(Path(__file__).parents[1]))

from bot import is_tiktok_url, is_youtube_url


def test_valid_tiktok_urls():
    assert is_tiktok_url("https://www.tiktok.com/@user/video/123456789")
    assert is_tiktok_url("https://tiktok.com/@user/video/123456789")
    assert is_tiktok_url("https://vm.tiktok.com/AbCd12/")
    assert is_tiktok_url("https://vt.tiktok.com/ZSqnGNH3B/")


def test_valid_youtube_urls():
    assert is_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert is_youtube_url("https://youtube.com/watch?v=dQw4w9WgXcQ&t=10s")


def test_invalid_urls():
    assert not is_tiktok_url("https://example.com/video.mp4")
    assert not is_tiktok_url("https://tiktok.com/@user/photo/123")
    assert not is_tiktok_url("not a url")
    assert not is_youtube_url("https://example.com/video.mp4")
    assert not is_youtube_url("not a url")
