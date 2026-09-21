import asyncio
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError, TimedOut
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from yt_dlp.utils import DownloadError

from config import ALLOWED_USER_ID, DOWNLOAD_DIR, MAX_FILE_SIZE_BYTES, TELEGRAM_BOT_TOKEN
from downloader import download_tiktok, download_with_gallery_dl, download_with_tiktok_api_dl, cleanup_downloads


load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

TIKTOK_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:tiktok\.com/@[^/\s]+/video/\d+|(?:vm|vt)\.tiktok\.com/[A-Za-z0-9]+/?)(?:\?.*)?$",
    re.IGNORECASE,
)
DOWNLOAD_LIMIT = asyncio.Semaphore(2)


def is_tiktok_url(text: str) -> bool:
    """Return True only for supported public TikTok URL shapes."""
    return bool(TIKTOK_URL_RE.fullmatch(text.strip()))


def is_allowed(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ALLOWED_USER_ID)


async def deny(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("❌ Kamu tidak diizinkan menggunakan bot ini.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    await update.effective_message.reply_text(
        "👋 Halo! Kirim link video TikTok publik untuk diunduh.\n\n"
        "Contoh:\nhttps://www.tiktok.com/@username/video/123456789\n\n"
        "Gunakan /help untuk bantuan."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    await update.effective_message.reply_text(
        "Kirim satu link video TikTok publik setiap kali.\n"
        "Bot tidak mendukung video private, login, DRM, atau link non-TikTok."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return

    message = update.effective_message
    text = (message.text or "").strip()
    if not is_tiktok_url(text):
        await message.reply_text(
            "❌ URL TikTok tidak valid.\n"
            "Silakan kirim link video TikTok yang dapat diakses secara publik."
        )
        return

    context.user_data["pending_url"] = text
    await message.reply_text(
        "Pilih kualitas video:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Biasa (lebih kecil)", callback_data="quality:normal"),
                InlineKeyboardButton("HD (lebih besar)", callback_data="quality:hd"),
            ]
        ]),
    )


async def handle_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or update.effective_user.id != ALLOWED_USER_ID:
        if query:
            await query.answer("Kamu tidak diizinkan menggunakan bot ini.", show_alert=True)
        return

    await query.answer()
    message = query.message
    if not message:
        return
    url = context.user_data.pop("pending_url", None)
    quality = query.data.split(":", 1)[1] if query.data else "normal"
    if not url or quality not in {"normal", "hd"}:
        await query.edit_message_text("❌ Permintaan download sudah tidak tersedia. Kirim URL TikTok lagi.")
        return

    status = await query.edit_message_text("⏳ Memproses video...")
    file_path: Path | None = None
    user_id = update.effective_user.id

    try:
        async with DOWNLOAD_LIMIT:
            logger.info("User %s requested download", user_id)
            try:
                file_path = await asyncio.to_thread(download_tiktok, url, quality)
            except Exception:
                logger.warning("yt-dlp could not access the public TikTok page for user %s", user_id)
                try:
                    file_path = await asyncio.to_thread(download_with_gallery_dl, url)
                except Exception as fallback_error:
                    logger.error("gallery-dl fallback failed for user %s: %s", user_id, fallback_error)
                    try:
                        file_path = await asyncio.to_thread(download_with_tiktok_api_dl, url)
                    except Exception as api_error:
                        logger.error("tiktok-api-dl fallback failed for user %s: %s", user_id, api_error)
                        raise DownloadError("TikTok page could not be accessed by available extractors") from api_error
        if not file_path.exists():
            raise FileNotFoundError("Downloaded file was not found")
        if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
            await status.edit_text("⚠️ Video berhasil diunduh, tetapi ukurannya terlalu besar untuk dikirim oleh bot.\n\nSilakan gunakan video yang lebih kecil.")
            return

        await status.edit_text("📥 Video berhasil diunduh.\n📤 Mengirim video...")
        logger.info("Upload started for user %s", user_id)
        with file_path.open("rb") as video:
            await message.reply_video(video=video, caption="✅ Selesai!")
        logger.info("Upload completed for user %s", user_id)
    except DownloadError:
        logger.exception("yt-dlp failed for user %s", user_id)
        try:
            await status.edit_text(
                "❌ TikTok tidak dapat diproses oleh yt-dlp saat ini.\n\n"
                "Pastikan video publik dan coba lagi setelah memperbarui yt-dlp."
            )
        except TelegramError:
            logger.exception("Could not update status message")
    except TimedOut:
        logger.warning("Telegram upload timed out for user %s", user_id)
        try:
            await status.edit_text(
                "❌ Upload ke Telegram timeout.\n\n"
                "Coba gunakan kualitas Biasa atau video yang lebih kecil."
            )
        except TelegramError:
            logger.warning("Could not update timeout status message")
    except Exception:
        logger.exception("Download or upload failed for user %s", user_id)
        try:
            await status.edit_text("❌ Gagal mengunduh video.\n\nPastikan:\n• URL TikTok valid\n• video dapat diakses secara publik\n• video tidak sedang dihapus/private")
        except TelegramError:
            logger.exception("Could not update status message")
    finally:
        if file_path:
            file_path.unlink(missing_ok=True)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled Telegram error: %s", context.error, exc_info=context.error)


def main() -> None:
    cleanup_downloads(DOWNLOAD_DIR)
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(90)
        .write_timeout(600)
        .pool_timeout(30)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_quality, pattern=r"^quality:(normal|hd)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    logger.info("Bot started")
    application.run_polling()


if __name__ == "__main__":
    main()
