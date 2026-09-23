import asyncio
import html
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError, TimedOut
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from yt_dlp.utils import DownloadError

from config import ALLOWED_USER_ID, DOWNLOAD_DIR, MAX_FILE_SIZE_BYTES, TELEGRAM_BOT_TOKEN, TIKTOK_URL_RE, YOUTUBE_URL_RE
from downloader import (
    cleanup_downloads,
    download_tiktok,
    download_with_gallery_dl,
    download_with_tiktok_api_dl,
    download_youtube,
    get_tiktok_user_posts,
    get_tiktok_user_reposts,
    stalk_tiktok_user,
)


load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

DOWNLOAD_LIMIT = asyncio.Semaphore(2)


def is_tiktok_url(text: str) -> bool:
    """Return True only for supported public TikTok URL shapes."""
    return bool(TIKTOK_URL_RE.fullmatch(text.strip()))


def is_youtube_url(text: str) -> bool:
    """Return True only for supported YouTube URL shapes."""
    return bool(YOUTUBE_URL_RE.fullmatch(text.strip()))


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
        "👋 <b>Selamat datang di Video Downloader</b>\n\n"
        "Kirim link video TikTok atau YouTube publik dan bot akan membantu mengunduhnya.\n\n"
        "<b>Cara menggunakan:</b>\n"
        "1. Kirim link TikTok atau YouTube\n"
        "2. Pilih kualitas video\n"
        "3. Tunggu proses selesai\n\n"
        "<b>Contoh:</b>\n"
        "<code>https://vt.tiktok.com/...</code>\n"
        "<code>https://youtu.be/...</code>\n\n"
        "Gunakan /help untuk bantuan.",
        parse_mode=ParseMode.HTML,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    await update.effective_message.reply_text(
        "❓ <b>Panduan Penggunaan Bot</b>\n\n"
        "<b>1. Download Video:</b>\n"
        "Kirim link TikTok atau YouTube publik langsung ke chat ini.\n\n"
        "<b>2. Fitur Stalk & Profil TikTok:</b>\n"
        "• <code>/stalk [username]</code>\n"
        "  <i>Contoh: <code>/stalk tiktok</code></i>\n"
        "  Melihat foto profil, followers, following, total like & status akun.\n\n"
        "• <code>/posts [username]</code>\n"
        "  <i>Contoh: <code>/posts tiktok</code></i>\n"
        "  Melihat 5 postingan video terbaru beserta statistiknya.\n\n"
        "• <code>/reposts [username]</code>\n"
        "  <i>Contoh: <code>/reposts tiktok</code></i>\n"
        "  Melihat 5 video yang di-repost oleh akun tersebut.",
        parse_mode=ParseMode.HTML,
    )


async def stalk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return

    if not context.args:
        await update.effective_message.reply_text(
            "⚠️ <b>Format salah</b>\n\n"
            "Gunakan format: <code>/stalk [username]</code>\n"
            "Contoh: <code>/stalk tiktok</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    username = context.args[0].strip().lstrip("@")
    status = await update.effective_message.reply_text(
        f"🔍 <b>Mencari profil @{username}...</b>",
        parse_mode=ParseMode.HTML,
    )

    try:
        profile_data = await asyncio.to_thread(stalk_tiktok_user, username)
        user = profile_data.get("user", {})
        stats = profile_data.get("stats", {})

        nickname = user.get("nickname") or username
        is_verified = " ✅" if user.get("verified") else ""
        is_private = "🔒 Akun Privat" if user.get("privateAccount") else "🌐 Akun Publik"
        signature = user.get("signature") or "<i>(Tidak ada bio)</i>"
        avatar_url = user.get("avatarLarger") or user.get("avatarMedium") or user.get("avatarThumb")

        followers = stats.get('followerCount', '0')
        if isinstance(followers, int):
            followers = f"{followers:,}"
        following = stats.get('followingCount', '0')
        if isinstance(following, int):
            following = f"{following:,}"
        total_likes = stats.get('heartCount', '0')
        if isinstance(total_likes, int):
            total_likes = f"{total_likes:,}"
        video_count = stats.get('videoCount', '-')
        if isinstance(video_count, int):
            video_count = f"{video_count:,}"

        caption = (
            f"👤 <b>Profil TikTok: {nickname}</b> (@{user.get('username', username)}){is_verified}\n\n"
            f"👥 <b>Followers:</b> {followers}\n"
            f"🚶‍♂️ <b>Following:</b> {following}\n"
            f"❤️ <b>Total Suka:</b> {total_likes}\n"
            f"🎬 <b>Total Video:</b> {video_count}\n"
            f"🛡️ <b>Status:</b> {is_private}\n\n"
            f"📝 <b>Bio:</b>\n{signature}"
        )

        if avatar_url:
            await update.effective_message.reply_photo(
                photo=avatar_url,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            await status.delete()
        else:
            await status.edit_text(caption, parse_mode=ParseMode.HTML)
    except Exception as err:
        logger.error("Stalk failed for user %s: %s", username, err)
        safe_err = html.escape(str(err))
        await status.edit_text(
            f"❌ <b>Gagal memeriksa profil:</b>\n<code>{safe_err}</code>",
            parse_mode=ParseMode.HTML,
        )


async def posts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return

    if not context.args:
        await update.effective_message.reply_text(
            "⚠️ <b>Format salah</b>\n\n"
            "Gunakan format: <code>/posts [username]</code>\n"
            "Contoh: <code>/posts tiktok</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    username = context.args[0].strip().lstrip("@")
    status = await update.effective_message.reply_text(
        f"⏳ <b>Mengambil postingan terbaru @{username}...</b>",
        parse_mode=ParseMode.HTML,
    )

    try:
        posts = await asyncio.to_thread(get_tiktok_user_posts, username, 5)
        if not posts:
            await status.edit_text(
                f"ℹ️ Akun @{username} belum memiliki postingan atau akun bersifat privat.",
                parse_mode=ParseMode.HTML,
            )
            return

        text_lines = [f"🎬 <b>Postingan Terbaru @{username}:</b>\n"]
        for idx, post in enumerate(posts, 1):
            desc = post.get("desc") or "(Tanpa deskripsi)"
            if len(desc) > 80:
                desc = desc[:77] + "..."
            post_id = post.get("id")
            stats = post.get("stats", {})
            likes = f"{stats.get('likeCount', 0):,}"
            plays = f"{stats.get('playCount', 0):,}"
            comments = f"{stats.get('commentCount', 0):,}"

            url = f"https://www.tiktok.com/@{username}/video/{post_id}" if post_id else "#"
            text_lines.append(
                f"<b>{idx}.</b> <a href=\"{url}\">{desc}</a>\n"
                f"   👁️ {plays} views | ❤️ {likes} likes | 💬 {comments} comments"
            )

        text_lines.append("\n💡 <i>Klik link video di atas untuk melihat atau copy link untuk download video.</i>")
        await status.edit_text("\n".join(text_lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as err:
        logger.error("Get posts failed for user %s: %s", username, err)
        safe_err = html.escape(str(err))
        await status.edit_text(
            f"❌ <b>Gagal mengambil postingan:</b>\n<code>{safe_err}</code>",
            parse_mode=ParseMode.HTML,
        )


async def reposts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return

    await update.effective_message.reply_text(
        "ℹ️ <b>Fitur Tidak Tersedia</b>\n\n"
        "Maaf, fitur pengambilan repostan TikTok sedang tidak tersedia karena pemblokiran WAF/anti-bot dari pihak TikTok.\n\n"
        "Kami terus bekerja untuk menemukan solusi alternatif. Silakan coba fitur lainnya:\n"
        "• <code>/stalk [username]</code> - Lihat profil TikTok\n"
        "• <code>/posts [username]</code> - Lihat postingan terbaru\n"
        "• Kirim link TikTok atau YouTube untuk download video",
        parse_mode=ParseMode.HTML,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return

    message = update.effective_message
    text = (message.text or "").strip()
    
    is_tiktok = is_tiktok_url(text)
    is_youtube = is_youtube_url(text)
    
    if not is_tiktok and not is_youtube:
        await message.reply_text(
            "❌ <b>URL tidak valid</b>\n\n"
            "Silakan kirim link TikTok atau YouTube yang dapat diakses secara publik.",
            parse_mode=ParseMode.HTML,
        )
        return

    platform = "TikTok" if is_tiktok else "YouTube"
    context.user_data["pending_url"] = text
    context.user_data["platform"] = platform
    await message.reply_text(
        f"🎬 <b>Video {platform} diterima</b>\n\n"
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
    platform = context.user_data.pop("platform", "TikTok")
    quality = query.data.split(":", 1)[1] if query.data else "normal"
    if not url or quality not in {"normal", "hd"}:
        await query.edit_message_text(
            f"❌ <b>Permintaan sudah tidak tersedia</b>\n\nKirim URL {platform} lagi.",
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
            logger.info("User %s requested %s download", user_id, platform)
            if platform == "YouTube":
                try:
                    file_path = await asyncio.to_thread(download_youtube, url, quality)
                except Exception as yt_error:
                    logger.error("YouTube download failed for user %s: %s", user_id, yt_error)
                    raise DownloadError("YouTube download failed") from yt_error
            else:
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
        logger.exception("Download failed for user %s", user_id)
        try:
            await status.edit_text(
                f"❌ <b>Download gagal</b>\n\n"
                f"{platform} tidak dapat memproses video ini saat ini. Pastikan video publik dan coba lagi.",
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
                f"❌ <b>Download gagal</b>\n\n"
                f"Pastikan:\n"
                f"• URL {platform} valid\n"
                f"• video dapat diakses secara publik\n"
                f"• video tidak sedang dihapus atau private",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            logger.exception("Could not update status message")
    finally:
        if file_path:
            file_path.unlink(missing_ok=True)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled Telegram error: %s", context.error, exc_info=context.error)


async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Mulai & info fitur bot"),
        BotCommand("help", "Panduan bantuan penggunaan"),
        BotCommand("stalk", "Cek profil & followers TikTok user"),
        BotCommand("posts", "Lihat postingan terbaru TikTok user"),
        BotCommand("reposts", "Lihat video repostan TikTok user"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands menu registered successfully")


def main() -> None:
    cleanup_downloads(DOWNLOAD_DIR)
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .connect_timeout(30)
        .read_timeout(90)
        .write_timeout(600)
        .pool_timeout(30)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stalk", stalk_command))
    application.add_handler(CommandHandler("posts", posts_command))
    application.add_handler(CommandHandler("reposts", reposts_command))
    application.add_handler(CallbackQueryHandler(handle_quality, pattern=r"^quality:(normal|hd)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    logger.info("Bot started")
    application.run_polling()


if __name__ == "__main__":
    main()
