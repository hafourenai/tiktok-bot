"""Cleanup guarantees for the conversion pipeline.

The conversion workspace holds both the uploaded file and the produced file,
so these tests pin down that nothing survives a run - not on success, and
especially not on failure, which is where an unclosed file handle used to leave
directories stranded on Windows.
"""

import os
import time
from pathlib import Path

import pytest

from converter.pipeline import get_workspace, new_workspace, cleanup_stale_workspaces
import converter


@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    """Point the converter workspace at a throwaway directory."""
    root = tmp_path / "workspace"
    monkeypatch.setattr("converter.pipeline.get_workspace", lambda: root)
    return root


def age(path: Path, seconds: int) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


# -- workspace creation ---------------------------------------------------
def test_new_workspace_is_unique_and_under_root(workspace_root):
    first = converter.new_workspace()
    second = converter.new_workspace()
    assert first != second
    assert Path(first).parent == workspace_root
    assert Path(first).is_dir()
    assert Path(second).is_dir()


# -- stale sweep ----------------------------------------------------------
def test_stale_workspace_is_removed(workspace_root):
    stale = converter.new_workspace()
    Path(stale, "out.pdf").write_bytes(b"x" * 50)
    age(Path(stale), converter.STALE_WORKSPACE_SECONDS + 60)

    removed = converter.cleanup_stale_workspaces()

    assert removed == [Path(stale).name]
    assert not Path(stale).exists()


def test_recent_workspace_is_left_alone(workspace_root):
    """A concurrent instance may be converting right now; do not touch it."""
    recent = converter.new_workspace()
    Path(recent, "in-flight.pdf").write_bytes(b"x")

    assert converter.cleanup_stale_workspaces() == []

    assert Path(recent).exists()
    assert Path(recent, "in-flight.pdf").exists()


def test_cleanup_leaves_files_at_the_root_untouched(workspace_root):
    """Only subdirectories are ours to delete; never stray files."""
    workspace_root.mkdir(parents=True, exist_ok=True)
    stray = workspace_root / "important.txt"
    stray.write_text("keep me")
    age(stray, converter.STALE_WORKSPACE_SECONDS * 10)

    converter.cleanup_stale_workspaces()

    assert stray.exists()
    assert stray.read_text() == "keep me"


def test_cleanup_is_idempotent(workspace_root):
    stale = converter.new_workspace()
    age(Path(stale), converter.STALE_WORKSPACE_SECONDS + 60)

    assert converter.cleanup_stale_workspaces() == [Path(stale).name]
    assert converter.cleanup_stale_workspaces() == []


def test_cleanup_with_no_workspace_directory(tmp_path, monkeypatch):
    missing = tmp_path / "never-created"
    monkeypatch.setattr("converter.pipeline.get_workspace", lambda: missing)
    assert cleanup_stale_workspaces() == []


def test_cleanup_never_escapes_the_workspace(tmp_path, monkeypatch):
    """The sweep must not follow symlinks or stray paths out of the root."""
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / "victim.txt"
    victim.write_text("must survive")

    root = tmp_path / "workspace"
    root.mkdir()
    link = root / "link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")

    monkeypatch.setattr(converter, "get_workspace", lambda: root)
    age(link, converter.STALE_WORKSPACE_SECONDS * 10)

    converter.cleanup_stale_workspaces()

    # shutil.rmtree does not follow directory symlinks, so the target survives.
    assert victim.exists()


# -- the bug this guards against -----------------------------------------
def test_closed_handle_allows_workspace_removal(tmp_path):
    """Regression: an open handle blocks rmtree on Windows."""
    import shutil

    root = tmp_path / "ws"
    root.mkdir()
    target = root / "out.pdf"
    target.write_bytes(b"data")

    # The corrected pattern used in bot.convert_callback.
    with open(target, "rb") as document:
        assert document.read() == b"data"

    shutil.rmtree(root, ignore_errors=False)
    assert not root.exists()


# -- integration with convert_callback ------------------------------------
def _make_callback_context(tmp_path, monkeypatch, send_impl=None):
    """Build the minimal update/context that convert_callback needs."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import bot

    root = tmp_path / "ws"

    def fake_workspace():
        root.mkdir(parents=True, exist_ok=True)
        return str(root)

    monkeypatch.setattr(bot, "new_workspace", fake_workspace)
    seen = {}

    def default_send(**kwargs):
        document = kwargs["document"]
        seen["sent"] = document.read()
        seen["handle_closed_later"] = True
        return AsyncMock(return_value=None)

    send = AsyncMock(side_effect=send_impl or default_send)

    def fake_download_to_drive(path):
        Path(path).write_bytes(b"%PDF-1.4 fake source")

    tg_file = SimpleNamespace(download_to_drive=AsyncMock(
        side_effect=fake_download_to_drive))

    bot_ctx = SimpleNamespace(get_file=AsyncMock(return_value=tg_file),
                              send_document=send)
    status = SimpleNamespace(delete=AsyncMock(), edit_text=AsyncMock())
    conv_token = "abc123def456"
    query = SimpleNamespace(data=f"convert:{conv_token}:docx",
                           answer=AsyncMock(),
                           edit_message_text=AsyncMock(return_value=status))
    update = SimpleNamespace(callback_query=query,
                             effective_user=SimpleNamespace(id=bot.ALLOWED_USER_ID),
                             effective_chat=SimpleNamespace(id=99, type="private"))
    context = SimpleNamespace(user_data={f"convert_{conv_token}": {
        "file_id": "FID1", "file_name": "invoice.pdf", "ext": ".pdf"}},
                             bot=bot_ctx)
    del asyncio
    return bot, query, update, context, send, root, seen


def test_compress_callback_sends_smaller_pdf_and_cleans_up(tmp_path, monkeypatch):
    import asyncio

    bot, query, update, context, send, root, seen = _make_callback_context(tmp_path, monkeypatch)
    query.data = "convert:abc123def456:compress_medium"

    def fake_compress(src, dst, level):
        assert level == "medium"
        assert Path(src).read_bytes().startswith(b"%PDF-")
        Path(dst).write_bytes(b"%PDF-1.4 small")
        return 1024, 14

    monkeypatch.setattr(bot, "compress_pdf", fake_compress)
    asyncio.run(bot.convert_callback(update, context))
    assert seen["sent"] == b"%PDF-1.4 small"
    assert "hemat" in send.call_args.kwargs["caption"]
    assert not root.exists()
    assert context.user_data == {}


def test_compress_callback_does_not_send_larger_pdf(tmp_path, monkeypatch):
    import asyncio

    bot, query, update, context, send, root, seen = _make_callback_context(tmp_path, monkeypatch)
    query.data = "convert:abc123def456:compress_high"
    monkeypatch.setattr(bot, "compress_pdf", lambda src, dst, level: (100, 120))
    asyncio.run(bot.convert_callback(update, context))
    send.assert_not_awaited()
    query.edit_message_text.return_value.edit_text.assert_awaited()
    assert not root.exists()


def test_convert_callback_cleans_up_after_success(tmp_path, monkeypatch):
    import asyncio

    from converter.lib.docconv.pdfwrite import write_text_pdf

    bot, query, update, context, send, root, seen = _make_callback_context(
        tmp_path, monkeypatch)

    def fake_convert(src, dst):
        write_text_pdf(["Invoice 123"], dst)
        return dst

    conv_token = "abc123def456"
    monkeypatch.setattr(bot, "convert_pdf_to_docx", fake_convert)

    asyncio.run(bot.convert_callback(update, context))

    assert send.await_count == 1
    # The delivered payload is the produced document, not the uploaded source.
    assert seen["sent"].startswith(b"%PDF-1.4")
    assert b"Invoice 123" not in seen["sent"]  # text is Flate-compressed
    # The whole workspace, input and output alike, is gone.
    assert not root.exists()
    # And the session entry is dropped, so uploads do not accumulate.
    assert f"convert_{conv_token}" not in context.user_data


def test_convert_callback_cleans_up_after_failure(tmp_path, monkeypatch):
    import asyncio

    bot, query, update, context, send, root, seen = _make_callback_context(
        tmp_path, monkeypatch)

    def boom(src, dst):
        raise RuntimeError("konversi gagal")

    conv_token = "abc123def456"
    monkeypatch.setattr(bot, "convert_pdf_to_docx", boom)

    asyncio.run(bot.convert_callback(update, context))

    assert send.await_count == 0
    # This is the case that used to strand the directory on Windows.
    assert not root.exists()
    assert f"convert_{conv_token}" not in context.user_data


def test_convert_callback_cleans_up_when_send_fails(tmp_path, monkeypatch):
    """A failing send is the real-world path that leaked directories."""
    import asyncio

    bot, query, update, context, send, root, seen = _make_callback_context(
        tmp_path, monkeypatch)

    async def failing_send(**kwargs):
        # Touch the handle first, mimicking a partial upload that errors out.
        kwargs["document"].read(1)
        raise RuntimeError("jaringan putus")

    send.side_effect = failing_send

    def fake_convert(src, dst):
        Path(dst).write_bytes(b"%PDF-1.4 produced")
        return dst

    monkeypatch.setattr(bot, "convert_pdf_to_docx", fake_convert)

    asyncio.run(bot.convert_callback(update, context))

    assert not root.exists()
    conv_token = "abc123def456"
    assert f"convert_{conv_token}" not in context.user_data


def test_expired_session_is_reported_without_touching_disk(tmp_path, monkeypatch):
    import asyncio

    bot, query, update, context, send, root, seen = _make_callback_context(
        tmp_path, monkeypatch)
    context.user_data.clear()

    asyncio.run(bot.convert_callback(update, context))

    assert send.await_count == 0
    query.edit_message_text.assert_awaited_once()
    assert "kedaluwarsa" in query.edit_message_text.await_args.args[0]
