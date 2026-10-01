import asyncio
import errno
import html
import logging
import os
import re
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from telegram import BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError, TimedOut
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from yt_dlp.utils import DownloadError

from config import (
    ALLOWED_USER_ID,
    DISCORD_BOT_TOKEN,
    DISCORD_GUILD_ID,
    DOWNLOAD_DIR,
    MAX_FILE_SIZE_BYTES,
    TELEGRAM_BOT_TOKEN,
    TIKTOK_FALLBACK_URL,
    TIMEZONE,
    TIKTOK_URL_RE,
    VOICE_DATABASE_PATH,
    VOICE_EXPORT_DIR,
    YOUTUBE_URL_RE,
)
from discord_voice import DiscordVoiceMonitor
from voice_export import export_period, format_duration
from voice_stats import VoiceStatsStore
from menus import menu_content, menu_commands
from downloader import (
    cleanup_downloads,
    download_tiktok,
    download_with_gallery_dl,
    download_with_tiktok_api_dl,
    download_youtube,
    stalk_tiktok_user,
)


load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

DOWNLOAD_LIMIT = asyncio.Semaphore(2)
UTC = timezone.utc


def is_local_file_error(error):
    return isinstance(error, OSError) and error.errno in {
        errno.EACCES, errno.EPERM, errno.ENOSPC, errno.EROFS, errno.ENOENT,
    }


def is_tiktok_url(text: str) -> bool:
    """Return True only for supported public TikTok URL shapes."""
    return bool(TIKTOK_URL_RE.fullmatch(text.strip()))


def is_youtube_url(text: str) -> bool:
    """Return True only for supported YouTube URL shapes."""
    return bool(YOUTUBE_URL_RE.fullmatch(text.strip()))


def is_allowed(update: Update) -> bool:
    return bool(
        update.effective_user
        and update.effective_user.id == ALLOWED_USER_ID
        and update.effective_chat
        and update.effective_chat.type == "private"
    )


async def deny(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "🔒 <b>Akses ditolak</b>\n\n"
            "Bot ini hanya dapat digunakan oleh pemilik yang dikonfigurasi.",
            parse_mode=ParseMode.HTML,
        )


def voice_store(context: ContextTypes.DEFAULT_TYPE) -> VoiceStatsStore:
    return context.application.bot_data["voice_store"]


def local_day_range(store: VoiceStatsStore, days: int = 1) -> tuple[datetime, datetime]:
    today = datetime.now(store.timezone).date()
    end = datetime.combine(today + timedelta(days=1), datetime.min.time(), store.timezone).astimezone(UTC)
    start = end - timedelta(days=days)
    return start, end


def month_range(store: VoiceStatsStore, period: str) -> tuple[datetime, datetime]:
    try:
        start_local = datetime.strptime(period, "%Y-%m").replace(tzinfo=store.timezone)
    except ValueError as error:
        raise ValueError("Gunakan format YYYY-MM, contoh: 2026-09") from error
    if start_local.month == 12:
        end_local = start_local.replace(year=start_local.year + 1, month=1)
    else:
        end_local = start_local.replace(month=start_local.month + 1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def summary_lines(summary: dict, limit: int = 3) -> str:
    top = list(summary["members"].items())[:limit]
    activities = "\n".join(f"{html.escape(name)} — {format_duration(seconds)}" for name, seconds in top) or "Belum ada aktivitas."
    return (
        f"Total Voice Time: <b>{format_duration(summary['total_seconds'])}</b>\n"
        f"Active Members: <b>{summary['active_members']}</b>\n"
        f"Sessions: <b>{summary['sessions']}</b>\n\n"
        f"<b>Top Activity:</b>\n{activities}"
    )


def member_channel_totals(store: VoiceStatsStore, summary: dict, start: datetime, end: datetime) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    now = datetime.now(UTC)
    for row in summary["rows"]:
        row_start = max(VoiceStatsStore._parse(row["joined_at"]), start)
        row_end = min(VoiceStatsStore._parse(row["left_at"]) if row["left_at"] else now, end)
        if row_end <= row_start:
            continue
        member = totals.setdefault(row["username"], {})
        member[row["channel_name"]] = member.get(row["channel_name"], 0) + int((row_end - row_start).total_seconds())
    return totals


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    store = voice_store(context)
    info = await asyncio.to_thread(store.storage_info)
    start = VoiceStatsStore._parse(info["oldest"]) if info["oldest"] else datetime.now(UTC)
    summary = await asyncio.to_thread(store.summarize, start, datetime.now(UTC))
    await update.effective_message.reply_text("📊 <b>Voice Activity</b>\n\n" + summary_lines(summary), parse_mode=ParseMode.HTML)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    store = voice_store(context)
    start, end = local_day_range(store)
    summary = await asyncio.to_thread(store.summarize, start, end)
    if not summary["members"]:
        text = "📊 <b>Voice Activity — Today</b>\n\nBelum ada aktivitas hari ini."
    else:
        lines = ["📊 <b>Voice Activity — Today</b>"]
        by_member = member_channel_totals(store, summary, start, end)
        for member, total in summary["members"].items():
            lines.extend(["", f"<b>{html.escape(member)}</b>"])
            for channel, seconds in sorted(by_member[member].items(), key=lambda item: item[1], reverse=True):
                lines.append(f"├─ {html.escape(channel)}: {format_duration(seconds)}")
            lines.append(f"Total: <b>{format_duration(total)}</b>")
        text = "\n".join(lines)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    days = 7
    if context.args:
        try:
            days = int(context.args[0])
            if not 1 <= days <= 365:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("⚠️ Gunakan /history 1 sampai 365.")
            return
    store = voice_store(context)
    start, end = local_day_range(store, days)
    summary = await asyncio.to_thread(store.summarize, start, end)
    await update.effective_message.reply_text(
        f"📊 <b>Voice Activity — {days} Hari Terakhir</b>\n\n" + summary_lines(summary, 10),
        parse_mode=ParseMode.HTML,
    )


async def storage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    info = await asyncio.to_thread(voice_store(context).storage_info)
    size_mb = info["size_bytes"] / (1024 * 1024)
    oldest = VoiceStatsStore._parse(info["oldest"]).astimezone(voice_store(context).timezone).date() if info["oldest"] else "-"
    newest = VoiceStatsStore._parse(info["newest"]).astimezone(voice_store(context).timezone).date() if info["newest"] else "-"
    await update.effective_message.reply_text(
        "💾 <b>Voice Storage</b>\n\n"
        f"Database size: <b>{size_mb:.2f} MB</b>\n"
        f"Total sessions: <b>{info['sessions']:,}</b>\n"
        f"Oldest record: <b>{oldest}</b>\nNewest record: <b>{newest}</b>",
        parse_mode=ParseMode.HTML,
    )


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    store = voice_store(context)
    period = context.args[0] if context.args else datetime.now(store.timezone).strftime("%Y-%m")
    try:
        start, end = month_range(store, period)
    except ValueError as error:
        await update.effective_message.reply_text(f"⚠️ {error}")
        return
    output = VOICE_EXPORT_DIR / f"voice_history_{period}.xlsx"
    status = await update.effective_message.reply_text("⏳ Membuat file Excel...")
    try:
        await asyncio.to_thread(export_period, store, start, end, output)
        with output.open("rb") as document:
            await update.effective_message.reply_document(document=document, filename=output.name, caption=f"✅ Export {period} selesai.")
        await asyncio.to_thread(store.mark_exported, period)
        try:
            await status.delete()
        except TelegramError:
            logger.warning("Could not remove export status message for %s", period)
        logger.info("[EXPORT] %s exported", period)
    except OSError as error:
        logger.exception("Excel file operation failed for %s", period)
        await status.edit_text(
            f"Export gagal saat mengakses file ({type(error).__name__}).\n"
            "Periksa izin folder dan ruang kosong dengan python check_environment.py."
        )
    except Exception:
        logger.exception("Excel export failed for %s", period)
        await status.edit_text("❌ Export gagal. Periksa log dan ruang penyimpanan Termux.")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    if len(context.args) != 1:
        await update.effective_message.reply_text("⚠️ Gunakan /delete YYYY-MM, contoh: /delete 2026-09")
        return
    store, period = voice_store(context), context.args[0]
    try:
        start, end = month_range(store, period)
    except ValueError as error:
        await update.effective_message.reply_text(f"⚠️ {error}")
        return
    count = await asyncio.to_thread(store.count_period, start, end)
    exported = await asyncio.to_thread(store.was_exported, period)
    status = "READY" if exported else "BELUM DI-EXPORT"
    await update.effective_message.reply_text(
        "⚠️ <b>PERINGATAN</b>\n\n"
        f"Anda akan menghapus: <b>{period}</b>\nJumlah session terdampak: <b>{count:,}</b>\nExport status: <b>{status}</b>\n\n"
        "Data yang dihapus tidak dapat dipulihkan dari database. Pastikan sudah melakukan /export terlebih dahulu.\n\n"
        f"Ketik <code>/confirm_delete {period}</code> untuk melanjutkan.",
        parse_mode=ParseMode.HTML,
    )


async def confirm_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return
    if len(context.args) != 1:
        await update.effective_message.reply_text("⚠️ Gunakan /confirm_delete YYYY-MM.")
        return
    store, period = voice_store(context), context.args[0]
    try:
        start, end = month_range(store, period)
    except ValueError as error:
        await update.effective_message.reply_text(f"⚠️ {error}")
        return
    if not await asyncio.to_thread(store.was_exported, period):
        await update.effective_message.reply_text(f"❌ Export bulan tersebut terlebih dahulu menggunakan:\n/export {period}")
        return
    try:
        deleted = await asyncio.to_thread(store.delete_period, start, end)
        await asyncio.to_thread(store.vacuum)
        logger.info("[DELETE] %s deleted (%s sessions)", period, deleted)
        await update.effective_message.reply_text(f"✅ {deleted:,} session untuk {period} telah dihapus dan database dibersihkan.")
    except Exception:
        logger.exception("Delete failed for %s", period)
        await update.effective_message.reply_text("❌ Penghapusan gagal. Tidak ada tindakan lanjutan yang dilakukan.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_menu(update, context, "home")


async def show_menu(update, context, section):
    if not is_allowed(update):
        if update.callback_query:
            await update.callback_query.answer("Akses ditolak.", show_alert=True)
        else:
            await deny(update)
        return
    context.user_data["menu"] = section
    text, keyboard = menu_content(section)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    await context.bot.set_my_commands(menu_commands(section), scope=BotCommandScopeChat(chat_id=ALLOWED_USER_ID))


async def category_command(update, context):
    section = update.effective_message.text.split()[0].split("@")[0].lstrip("/")
    await show_menu(update, context, section)


async def menu_callback(update, context):
    await show_menu(update, context, update.callback_query.data.split(":", 1)[1])


async def action_callback(update, context):
    if not is_allowed(update):
        await update.callback_query.answer("Akses ditolak.", show_alert=True)
        return
    await update.callback_query.answer()
    context.args = []
    handlers = {"stats": stats_command, "today": today_command, "history": history_command,
                "export": export_command, "storage": storage_command}
    await handlers[update.callback_query.data.split(":", 1)[1]](update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_menu(update, context, context.user_data.get("menu", "home"))


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


def build_download_failure(platform: str) -> str:
    """Return a user-facing failure notice, pointing TikTok users to the web fallback."""
    if platform == "TikTok":
        return (
            "❌ <b>Download TikTok gagal</b>\n\n"
            "<b>Kemungkinan penyebab:</b>\n"
            "• Rate limit / anti-bot TikTok (WAF memblokir akses otomatis)\n"
            "• Video privat, dihapus, atau dibatasi region\n"
            "• CDN video tidak bisa diakses dari server ini\n\n"
            "<b>Solusi:</b>\n"
            f"Download manual via: <a href=\"{TIKTOK_FALLBACK_URL}\">{TIKTOK_FALLBACK_URL}</a>\n\n"
            "<i>Coba lagi beberapa menit lagi, atau gunakan situs di atas.</i>"
        )
    return (
        "❌ <b>Download gagal</b>\n\n"
        f"{platform} tidak dapat memproses video ini saat ini.\n"
        "Pastikan video publik dan coba lagi."
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
    request_id = uuid4().hex[:12]
    pending = context.user_data.setdefault("downloads", {})
    if len(pending) >= 20:
        pending.pop(next(iter(pending)))
    pending[request_id] = (text, platform)
    await message.reply_text(
        f"🎬 <b>Video {platform} diterima</b>\n\n"
        "Pilih kualitas download:\n"
        "• Biasa: ukuran lebih kecil\n"
        "• HD: kualitas lebih tinggi, ukuran lebih besar",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Biasa (lebih kecil)", callback_data=f"quality:normal:{request_id}"),
                InlineKeyboardButton("HD (lebih besar)", callback_data=f"quality:hd:{request_id}"),
            ]
        ]),
    )


async def handle_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not is_allowed(update):
        if query:
            await query.answer("Kamu tidak diizinkan menggunakan bot ini.", show_alert=True)
        return

    await query.answer()
    message = query.message
    if not message:
        return
    parts = (query.data or "").split(":")
    quality = parts[1] if len(parts) > 1 else ""
    request_id = parts[2] if len(parts) > 2 else ""
    url, platform = context.user_data.get("downloads", {}).pop(request_id, (None, "video"))
    if not url or quality not in {"normal", "hd"}:
        await query.edit_message_text(
            f"❌ <b>Permintaan sudah tidak tersedia</b>\n\nKirim URL {platform} lagi.",
            parse_mode=ParseMode.HTML,
        )
        return

    status = await query.edit_message_text(
        "⏳ <b>Permintaan diterima</b>\nMenunggu slot download...",
        parse_mode=ParseMode.HTML,
    )
    file_path: Path | None = None
    user_id = update.effective_user.id

    try:
        async with DOWNLOAD_LIMIT:
            await status.edit_text(f"Mengunduh video {platform} ({'HD' if quality == 'hd' else 'Biasa'})...\nMengambil media dan menyiapkan file.")
            logger.info("User %s requested %s download", user_id, platform)
            if platform == "YouTube":
                try:
                    file_path = await asyncio.to_thread(download_youtube, url, quality)
                except Exception as yt_error:
                    if is_local_file_error(yt_error):
                        raise
                    logger.error("YouTube download failed for user %s: %s", user_id, yt_error)
                    raise DownloadError("YouTube download failed") from yt_error
            else:
                try:
                    file_path = await asyncio.to_thread(download_tiktok, url, quality)
                except Exception as primary_error:
                    if is_local_file_error(primary_error):
                        raise
                    await status.edit_text("Metode utama belum berhasil. Mencoba downloader cadangan (2/3)...")
                    logger.warning("yt-dlp could not access the public TikTok page for user %s", user_id)
                    try:
                        file_path = await asyncio.to_thread(download_with_gallery_dl, url)
                    except Exception as fallback_error:
                        if is_local_file_error(fallback_error):
                            raise
                        await status.edit_text("Mencoba downloader cadangan terakhir (3/3)...")
                        logger.error("gallery-dl fallback failed for user %s: %s", user_id, fallback_error)
                        try:
                            file_path = await asyncio.to_thread(download_with_tiktok_api_dl, url)
                        except Exception as api_error:
                            if is_local_file_error(api_error):
                                raise
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
            f"✅ <b>Download selesai</b>\nUkuran: {file_path.stat().st_size / (1024 * 1024):.1f} MB\n\n📤 Mengirim video ke Telegram...",
            parse_mode=ParseMode.HTML,
        )
        logger.info("Upload started for user %s", user_id)
        with file_path.open("rb") as video:
            await message.reply_video(
                video=video,
                caption="🎉 <b>Video berhasil dikirim!</b>",
                parse_mode=ParseMode.HTML,
            )
        logger.info("Upload completed for user %s", user_id)
        try:
            await status.edit_text("Selesai — video berhasil dikirim.")
        except TelegramError:
            logger.warning("Could not update completed download status")
    except OSError as error:
        logger.exception("Local file or dependency error")
        await status.edit_text(
            "Proses file gagal. Periksa izin folder, ruang kosong, dan program pendukung.\n"
            "Jalankan python check_environment.py di Termux untuk diagnosis.\n"
            f"Jenis error: {type(error).__name__}"
        )
    except DownloadError:
        logger.exception("Download failed for user %s", user_id)
        try:
            await status.edit_text(
                build_download_failure(platform),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
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
                build_download_failure(platform),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except TelegramError:
            logger.exception("Could not update status message")
    finally:
        if file_path:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Could not clean up downloaded file")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled Telegram error: %s", context.error, exc_info=context.error)


async def post_init(application: Application) -> None:
    await application.bot.delete_my_commands()
    await application.bot.set_my_commands(menu_commands("home"), scope=BotCommandScopeChat(chat_id=ALLOWED_USER_ID))
    monitor = application.bot_data.get("discord_monitor")
    if monitor and DISCORD_BOT_TOKEN:
        application.create_task(monitor.start(DISCORD_BOT_TOKEN), name="discord-voice-monitor")
        logger.info("Discord voice monitor task started")
    elif not DISCORD_BOT_TOKEN:
        logger.warning("DISCORD_BOT_TOKEN is not configured; voice monitoring is disabled")
    logger.info("Bot commands menu registered successfully")


async def post_shutdown(application: Application) -> None:
    monitor = application.bot_data.get("discord_monitor")
    if monitor and not monitor.is_closed():
        await monitor.close()


def main() -> None:
    cleanup_downloads(DOWNLOAD_DIR)
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .connect_timeout(30)
        .read_timeout(90)
        .write_timeout(600)
        .pool_timeout(30)
        .build()
    )
    store = VoiceStatsStore(VOICE_DATABASE_PATH, TIMEZONE)
    application.bot_data["voice_store"] = store
    application.bot_data["discord_monitor"] = DiscordVoiceMonitor(store, DISCORD_GUILD_ID)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler(["downloader", "discord"], category_command))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:(home|downloader|discord)$"))
    application.add_handler(CallbackQueryHandler(action_callback, pattern=r"^action:(stats|today|history|export|storage)$"))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stalk", stalk_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("confirm_delete", confirm_delete_command))
    application.add_handler(CommandHandler("storage", storage_command))
    application.add_handler(CallbackQueryHandler(handle_quality, pattern=r"^quality:(normal|hd)(:[a-f0-9]{12})?$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    logger.info("Bot started")
    application.run_polling()


if __name__ == "__main__":
    main()
