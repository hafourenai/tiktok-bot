import pytest

from config import INSTAGRAM_URL_RE


@pytest.mark.parametrize("url", [
    "https://www.instagram.com/reel/DdxbmN3SHE6/?utm_source=ig_web_copy_link&dlrf=MzRlODBiNWFlZA==&srtk=MzRlODBiNWFlZA==",
    "https://www.instagram.com/reel/DdxbmN3SHE6/",
    "https://instagram.com/reel/DdxbmN3SHE6",
    "https://instagram.com/reel/DdxbmN3SHE6?utm_source=test",
    "https://instagram.com/p/ABC_123-/",
    "https://instagram.com/tv/ABC123/",
    "https://instagram.com/stories/user.name/123456789/",
    "https://instagram.com/p/ABC123/#fragment",
])
def test_supported_instagram_urls(url):
    assert INSTAGRAM_URL_RE.fullmatch(url)


@pytest.mark.parametrize("url", [
    "https://instagram.com/",
    "https://instagram.com/reel/",
    "https://instagram.com/reel/ABC123/extra",
    "https://instagram.com.evil.example/reel/ABC123/",
    "https://evil.example/instagram.com/reel/ABC123/",
    "https://instagram.com/reel/ABC123/?text=two words",
])
def test_invalid_instagram_urls(url):
    assert not INSTAGRAM_URL_RE.fullmatch(url)
