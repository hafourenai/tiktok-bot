import os
import sys
import asyncio
from unittest.mock import AsyncMock
from pathlib import Path
from types import SimpleNamespace

os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["ALLOWED_TELEGRAM_USER_ID"] = "123"
sys.path.insert(0, str(Path(__file__).parents[1]))

from bot import is_allowed, is_tiktok_url, is_youtube_url


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


def test_access_is_limited_to_owner_private_chat():
    owner_private = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(type="private"),
    )
    owner_group = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(type="group"),
    )
    other_private = SimpleNamespace(
        effective_user=SimpleNamespace(id=456),
        effective_chat=SimpleNamespace(type="private"),
    )

    assert is_allowed(owner_private)
    assert not is_allowed(owner_group)
    assert not is_allowed(other_private)


def test_menu_navigation_updates_commands():
    from bot import show_menu

    async def scenario():
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_user=SimpleNamespace(id=123),
                                 effective_chat=SimpleNamespace(type="private"),
                                 effective_message=message, callback_query=None)
        context = SimpleNamespace(user_data={}, bot=SimpleNamespace(set_my_commands=AsyncMock()))
        await show_menu(update, context, "home")
        keyboard = message.reply_text.call_args.kwargs["reply_markup"]
        assert [button.text for button in keyboard.inline_keyboard[0]] == ["Downloader", "Discord"]
        update.callback_query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
        await show_menu(update, context, "discord")
        commands = context.bot.set_my_commands.call_args.args[0]
        assert "stats" in [item.command for item in commands]
        assert "stalk" not in [item.command for item in commands]
        await show_menu(update, context, "downloader")
        commands = context.bot.set_my_commands.call_args.args[0]
        assert "stalk" in [item.command for item in commands]
        assert "stats" not in [item.command for item in commands]

    asyncio.run(scenario())


def test_quality_buttons_keep_their_own_url(monkeypatch, tmp_path):
    import bot

    async def scenario():
        message = SimpleNamespace(reply_text=AsyncMock(), reply_video=AsyncMock())
        update = SimpleNamespace(effective_user=SimpleNamespace(id=123),
                                 effective_chat=SimpleNamespace(type="private"),
                                 effective_message=message)
        context = SimpleNamespace(user_data={})
        message.text = "https://youtu.be/dQw4w9WgXcQ"
        await bot.handle_message(update, context)
        first_button = message.reply_text.call_args.kwargs["reply_markup"].inline_keyboard[0][0]
        message.text = "https://youtu.be/abcdefghijk"
        await bot.handle_message(update, context)
        downloaded = tmp_path / "result.mp4"
        downloaded.write_bytes(b"video")
        seen = []

        def download(url, quality):
            seen.append(url)
            return downloaded

        monkeypatch.setattr(bot, "download_youtube", download)
        status = SimpleNamespace(edit_text=AsyncMock())
        update.callback_query = SimpleNamespace(data=first_button.callback_data, message=message,
                                               answer=AsyncMock(), edit_message_text=AsyncMock(return_value=status))
        await bot.handle_quality(update, context)
        assert seen == ["https://youtu.be/dQw4w9WgXcQ"]
        assert len(context.user_data["downloads"]) == 1
        message.reply_video.assert_awaited_once()
        assert not downloaded.exists()
        assert "berhasil dikirim" in status.edit_text.call_args.args[0]
        await bot.handle_quality(update, context)
        assert len(seen) == 1

    asyncio.run(scenario())
