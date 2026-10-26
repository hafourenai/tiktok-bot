"""Telegram bot handlers for news."""
import asyncio
import html
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.news.fetcher import clean_feed_text
from src.news.sources import publisher_for_source

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
FALLBACK_LABEL = "Cuplikan sumber (tanpa ringkasan AI)"


def format_article_message(article, summary: str, origin: str, number: int) -> str:
    """Format single article for Telegram."""
    # Both RSS and model output are untrusted and may contain markup. Strip it
    # before Telegram HTML escaping so tags are not displayed literally.
    clean_summary = clean_feed_text(summary, limit=1200)
    if origin == "source_excerpt":
        clean_summary = f"{FALLBACK_LABEL}: {clean_summary}"
    publisher = publisher_for_source(article.source_id)
    safe_url = html.escape(article.canonical_url, quote=True)
    return (
        f"<b>{number}. {html.escape(article.title)}</b>\n\n"
        f"📰 <b>{html.escape(publisher)}</b> — "
        f"{html.escape(clean_summary or 'Ringkasan belum tersedia.')}\n"
        f"🔗 <a href=\"{safe_url}\">{safe_url}</a>"
    )


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split long message into Telegram-safe chunks."""
    if len(text) <= max_length:
        return [text]
    
    messages = []
    current = ""
    
    # Split by double newlines first (article separators)
    parts = text.split("\n\n")
    
    for part in parts:
        if len(part) > max_length:
            if current:
                messages.append(current)
                current = ""
            messages.extend(
                part[index:index + max_length]
                for index in range(0, len(part), max_length)
            )
            continue
        if len(current) + len(part) + 2 > max_length:
            if current:
                messages.append(current)
            current = part
        else:
            if current:
                current += "\n\n"
            current += part
    
    if current:
        messages.append(current)
    
    return messages


async def berita_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /berita command."""
    from src.news.sources import get_all_categories
    
    # Note: access control is done at bot.py handler level
    # Get category from args
    category = None
    if context.args:
        category = context.args[0].strip().lower()
        
        # Validate category
        if category not in get_all_categories():
            valid_cats = ", ".join(get_all_categories())
            await update.effective_message.reply_text(
                f"❌ <b>Kategori tidak dikenal</b>\n\n"
                f"Kategori yang tersedia:\n{valid_cats}\n\n"
                f"Gunakan: /berita atau /berita [kategori]",
                parse_mode=ParseMode.HTML,
            )
            return
    
    chat_id = update.effective_chat.id
    active_chats = context.application.bot_data.setdefault("news_active_chats", set())
    if chat_id in active_chats:
        await update.effective_message.reply_text(
            "⏳ Permintaan berita sebelumnya masih diproses. Tunggu hingga selesai."
        )
        return
    active_chats.add(chat_id)

    # Send status
    status = await update.effective_message.reply_text(
        "⏳ Mengambil berita terbaru...",
        parse_mode=ParseMode.HTML,
    )
    
    try:
        # Get service
        service = context.application.bot_data.get("news_service")
        if not service:
            await status.edit_text(
                "❌ Layanan berita sedang tidak tersedia.",
                parse_mode=ParseMode.HTML,
            )
            return
        
        # Enforce one deadline around feed, extraction, and all inference.
        result = await asyncio.wait_for(
            service.fetch_news(category),
            timeout=context.application.bot_data.get("news_total_timeout", 180),
        )
        
        if result.error and not result.articles:
            await status.edit_text(
                f"❌ {html.escape(result.error)}\n\n"
                "Coba lagi dalam beberapa saat.",
                parse_mode=ParseMode.HTML,
            )
            return
        
        if not result.articles:
            await status.edit_text(
                "📭 Belum berhasil mengambil berita terbaru. Coba lagi.",
                parse_mode=ParseMode.HTML,
            )
            return
        
        # Build messages
        article_messages = []
        for i, article in enumerate(result.articles, 1):
            summary = result.summaries.get(article.canonical_url, article.excerpt)
            origin = result.summary_origins.get(article.canonical_url, "source_excerpt")
            article_messages.append(format_article_message(article, summary, origin, i))

        heading = f"📰 <b>Berita Terbaru{' — ' + category.capitalize() if category else ''}</b>"
        full_text = "\n\n".join([heading, *article_messages])
        
        # Split and send
        messages = split_message(full_text)
        
        for msg_text in messages:
            await update.effective_message.reply_text(
                msg_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        
        # Clean up status
        try:
            await status.delete()
        except Exception:
            pass
        
        logger.info("Sent %d articles", len(result.articles))
    
    except asyncio.TimeoutError:
        await status.edit_text(
            "⏱️ <b>Waktu habis</b>\n\n"
            "Permintaan memakan waktu terlalu lama. Coba lagi.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.exception("News command error")
        await status.edit_text(
            "❌ <b>Terjadi kesalahan</b>\n\n"
            "Silakan coba lagi.",
            parse_mode=ParseMode.HTML,
        )
    finally:
        active_chats.discard(chat_id)
