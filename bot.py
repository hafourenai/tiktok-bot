import asyncio
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
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
        await update.effective_message.reply_text(
            "🔒 <b>Akses ditolak</b>\n\n"
            "Bot ini hanya dapat digunakan oleh pemilik yang dikonfigurasi.",
            parse_mode=ParseMode.HTML,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    await update.effective_message.reply_text(
        "👋 <b>Selamat datang di TikTok Downloader</b>\n\n"
        "Kirim link video TikTok publik dan bot akan membantu mengunduhnya.\n\n"
        "<b>Cara menggunakan:</b>\n"
        "1. Kirim link TikTok\n"
        "2. Pilih kualitas video\n"
        "3. Tunggu proses selesai\n\n"
        "<b>Contoh:</b>\n"
        "<code>https://vt.tiktok.com/...</code>\n\n"
        "Gunakan /help untuk bantuan.",
        parse_mode=ParseMode.HTML,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    await update.effective_message.reply_text(
        "❓ <b>Bantuan</b>\n\n"
        "Kirim satu link video TikTok publik setiap kali, lalu pilih kualitas yang diinginkan.\n\n"
        "<b>Didukung:</b>\n"
        "• Link TikTok panjang\n"
        "• Link <code>vm.tiktok.com</code>\n"
        "• Link <code>vt.tiktok.com</code>\n\n"
        "<b>Tidak didukung:</b>\n"
        "• Video private\n"
        "• Video yang membutuhkan login\n"
        "• DRM atau access control",
        parse_mode=ParseMode.HTML,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return

    message = update.effective_message
    text = (message.text or "").strip()
    if not is_tiktok_url(text):
        await message.reply_text(
            "❌ <b>URL TikTok tidak valid</b>\n\n"
            "Silakan kirim link video TikTok yang dapat diakses secara publik.",
            parse_mode=ParseMode.HTML,
        )
        return

    context.user_data["pending_url"] = text
    await message.reply_text(
        "🎬 <b>Video TikTok diterima</b>\n\n"
        "Pilih kualitas download:\n"
        "• Biasa: ukuran lebih kecil\n"
        "• HD: kualitas lebih tinggi, ukuran lebih besar",
        parse_mode=ParseMode.HTML,
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
        await query.edit_message_text(
            "❌ <b>Permintaan sudah tidak tersedia</b>\n\nKirim URL TikTok lagi.",
            parse_mode=ParseMode.HTML,
        )
        return

    status = await query.edit_message_text(
        "⏳ <b>Menyiapkan download...</b>",
        parse_mode=ParseMode.HTML,
    )
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
            await status.edit_text(
                "⚠️ <b>Video terlalu besar</b>\n\n"
                "Video berhasil diunduh, tetapi ukurannya melebihi batas Telegram.\n"
                "Silakan pilih video yang lebih kecil.",
                parse_mode=ParseMode.HTML,
            )
            return

        await status.edit_text(
            "✅ <b>Download selesai</b>\n\n📤 Mengirim video ke Telegram...",
            parse_mode=ParseMode.HTML,
        )
        logger.info("Upload started for user %s", user_id)
        with file_path.open("rb") as video:
            await message.reply_video(
                video=video,
                caption="🎉 <b>Video berhasil dikirim!</b>\n\nFile tadi udah dibersihin.",
                parse_mode=ParseMode.HTML,
            )
        logger.info("Upload completed for user %s", user_id)
    except DownloadError:
        logger.exception("yt-dlp failed for user %s", user_id)
        try:
            await status.edit_text(
                "❌ <b>Download gagal</b>\n\n"
                "TikTok tidak dapat memproses video ini saat ini. Pastikan video publik dan coba lagi.",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            logger.exception("Could not update status message")
    except TimedOut:
        logger.warning("Telegram upload timed out for user %s", user_id)
        try:
            await status.edit_text(
                "⏱️ <b>Upload timeout</b>\n\n"
                "Coba gunakan kualitas Biasa atau video yang lebih kecil.",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            logger.warning("Could not update timeout status message")
    except Exception:
        logger.exception("Download or upload failed for user %s", user_id)
        try:
            await status.edit_text(
                "❌ <b>Download gagal</b>\n\n"
                "Pastikan:\n"
                "• URL TikTok valid\n"
                "• video dapat diakses secara publik\n"
                "• video tidak sedang dihapus atau private",
                parse_mode=ParseMode.HTML,
            )
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
