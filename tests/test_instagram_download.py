import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from downloader import download_instagram
from menus import menu_content


def test_instagram_menu():
    text, _ = menu_content("downloader")
    assert "Instagram" in text
    assert "Carousel" in text


@pytest.mark.parametrize("media_type,extension", [("video", ".mp4"), ("photo", ".jpg")])
def test_instagram_download_type(tmp_path, media_type, extension):
    response = MagicMock(returncode=0, stderr="", stdout=json.dumps({
        "status": "success", "url": "https://cdn.example/media", "mediaType": media_type,
    }))
    stream = MagicMock()
    stream.__enter__.return_value.read.side_effect = [b"media", b""]
    with patch("config.DOWNLOAD_DIR", str(tmp_path)), patch("downloader.subprocess.run", return_value=response), patch("downloader.urlopen", return_value=stream):
        result = download_instagram("https://instagram.com/reel/BA/")
    assert result.suffix == extension
    assert result.read_bytes() == b"media"


def test_instagram_login_error_is_actionable(tmp_path):
    response = MagicMock(returncode=1, stderr="Instagram login failed.", stdout="")
    with patch("config.DOWNLOAD_DIR", str(tmp_path)), patch("downloader.subprocess.run", return_value=response):
        with pytest.raises(RuntimeError, match="Login Instagram gagal"):
            download_instagram("https://instagram.com/reel/BA/")


def test_instagram_credentials_required_is_distinct_from_login_failure(tmp_path):
    response = MagicMock(returncode=1, stderr="Instagram credentials required.", stdout="")
    with patch("config.DOWNLOAD_DIR", str(tmp_path)), patch("downloader.subprocess.run", return_value=response):
        with pytest.raises(RuntimeError, match="credentials missing"):
            download_instagram("https://instagram.com/reel/BA/")


@pytest.mark.parametrize("extension,method", [(".mp4", "reply_video"), (".jpg", "reply_photo")])
def test_instagram_telegram_upload(monkeypatch, tmp_path, extension, method):
    import bot

    file_path = tmp_path / ("media" + extension)
    file_path.write_bytes(b"media")
    monkeypatch.setattr(bot, "download_instagram", lambda url: file_path)
    monkeypatch.setattr(bot, "ALLOWED_USER_ID", 123)
    message = SimpleNamespace(reply_video=AsyncMock(), reply_photo=AsyncMock())
    status = SimpleNamespace(edit_text=AsyncMock())
    query = SimpleNamespace(data="quality:normal:test", message=message,
                            answer=AsyncMock(), edit_message_text=AsyncMock(return_value=status))
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=123),
                             effective_chat=SimpleNamespace(type="private"))
    context = SimpleNamespace(user_data={"downloads": {"test": ("https://instagram.com/reel/BA/", "Instagram")}})
    asyncio.run(bot.handle_quality(update, context))
    getattr(message, method).assert_awaited_once()
    other = "reply_photo" if method == "reply_video" else "reply_video"
    getattr(message, other).assert_not_awaited()
    assert not file_path.exists()
