"""Telegram bot handlers for news."""
import asyncio
import html
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Asia/Jakarta")
MAX_MESSAGE_LENGTH = 4096
FALLBACK_LABEL = "Cuplikan sumber (tanpa ringkasan AI)"


def format_article_message(article, summary: str, timezone=TIMEZONE) -> str:
    """Format single article for Telegram."""
    # Convert UTC to Jakarta time
    if article.published_at_utc.tzinfo is None:
        pub_time = article.published_at_utc.replace(tzinfo=timezone.utc)
    else:
        pub_time = article.published_at_utc
    
    pub_time_jkt = pub_time.astimezone(TIMEZONE)
    time_str = pub_time_jkt.strftime("%d %b %Y %H:%M WIB")
    
    # Determine if this is AI summary or fallback
    is_fallback = summary == article.excerpt
    
    lines = [
        f"<b>{html.escape(article.title)}</b>",
        "",
        f"📰 {html.escape(article.source_id)}",
        f"🕐 {time_str}",
        "",
    ]
    
    if is_fallback:
        lines.append(f"<i>{FALLBACK_LABEL}:</i>")
    else:
        lines.append("<i>📌 Ringkasan:</i>")
    
    lines.append(html.escape(summary))
    lines.append("")
    lines.append(f"<a href=\"{html.escape(article.canonical_url)}\">Baca artikel lengkap →</a>")
    
    return "\n".join(lines)


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split long message into Telegram-safe chunks."""
    if len(text) <= max_length:
        return [text]
    
    messages = []
    current = ""
    
    # Split by double newlines first (article separators)
    parts = text.split("\n\n")
    
    for part in parts:
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
        
        # Fetch news
        result = await service.fetch_news(category)
        
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
        header_lines = [
            f"📰 <b>Berita Terbaru{' — ' + category.capitalize() if category else ''}</b>",
            "",
        ]
        
        if result.cached:
            time_str = result.fetch_time.astimezone(TIMEZONE).strftime("%H:%M WIB")
            header_lines.append(f"<i>💾 Hasil tersimpan dari {time_str}</i>")
            header_lines.append("")
        
        article_messages = []
        for i, article in enumerate(result.articles, 1):
            summary = result.summaries.get(article.canonical_url, article.excerpt)
            msg = format_article_message(article, summary, timezone=TIMEZONE)
            article_messages.append(f"<b>{i}.</b>\n{msg}")
        
        full_text = "\n\n".join(header_lines + article_messages)
        
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
