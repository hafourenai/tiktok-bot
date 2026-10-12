import asyncio
import errno
import html
import logging
import os
import re
import shutil
import tempfile
import time
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from telegram import (BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup,
                      KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update)
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
    WEATHER_GEOCODER_URL,
    YOUTUBE_URL_RE,
    INSTAGRAM_URL_RE,
)
from discord_voice import DiscordVoiceMonitor
from voice_export import export_period, format_duration
from voice_stats import VoiceStatsStore
from menus import menu_content, menu_commands
from bmkg_location_resolver import WeatherError, WeatherService, RegionSelectionRequired
from bmkg_location_resolver.resolver import match_region, normalized_name, region_code_pattern
from bmkg_location_resolver.telegram import coordinates_from_message
try:
    from weather_card import generate_weather_card
    HAS_WEATHER_CARD = True
except ImportError:
    generate_weather_card = None
    HAS_WEATHER_CARD = False

try:
    from src.converter import (
        SUPPORTED_EXTENSIONS,
        cleanup_stale_workspaces,
        convert_pdf_to_docx,
        convert_pdf_to_xlsx,
        convert_pdf_to_pptx,
        convert_pdf_to_images,
        convert_image_to_pdf,
        convert_office_to_pdf,
        new_workspace,
    )
    HAS_CONVERTER = True
except ImportError:
    SUPPORTED_EXTENSIONS = {}
    HAS_CONVERTER = False

    def new_workspace():
        return tempfile.mkdtemp(prefix="convert-")

    def cleanup_stale_workspaces():
        return []

from downloader import (
    cleanup_downloads,
    download_tiktok,
    download_with_gallery_dl,
    download_with_tiktok_api_dl,
    download_youtube,
    download_instagram,
    get_instagram_info,
    stalk_tiktok_user,
)


load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

DOWNLOAD_LIMIT = asyncio.Semaphore(2)
UTC = timezone.utc
WEATHER_REQUEST_TTL = 300
WEATHER_LOCATION_FILTER = filters.LOCATION | filters.VENUE
WEATHER_MANUAL_LABEL = "Input wilayah manual"
WEATHER_REGION_LABELS = ("provinsi", "kota/kabupaten", "kecamatan", "kelurahan/desa")
WEATHER_PAGE_SIZE = 20
WEATHER_NEXT = "wr_next"
WEATHER_PREVIOUS = "wr_prev"
WEATHER_ALL = "wr_all"
WEATHER_CANCEL = "wr_cancel"


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


def is_instagram_url(text: str) -> bool:
    """Return True only for supported Instagram URL shapes."""
    return bool(INSTAGRAM_URL_RE.fullmatch(text.strip()))


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


async def weather_command(update, context):
    if not is_allowed(update):
        await deny(update)
        return
    context.user_data["weather_request"] = time.time()
    context.user_data.pop("weather_manual", None)
    await update.effective_message.reply_text(
        "🌦 <b>Cuaca Indonesia</b>\nPrakiraan resmi BMKG untuk wilayah Anda.\n\n"
        "<b>Input wilayah manual</b>\nPilih provinsi, kota/kabupaten, kecamatan, lalu kelurahan/desa.\n\n"
        "<b>Kirim lokasi saya</b>\nGunakan tombol atau Lampiran → Lokasi. Titik peta dan tempat bernama juga didukung.\n\n"
        "Lokasi GPS diteruskan ke OpenStreetMap untuk pemetaan. Pilihan wilayah hanya dipakai sekali, "
        "tanpa lokasi default tersimpan. Gunakan lokasi statis, bukan live location.\n"
        "/batal untuk membatalkan · berlaku 5 menit.",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            [[WEATHER_MANUAL_LABEL], [KeyboardButton("Kirim lokasi saya", request_location=True)], ["/batal"]],
            resize_keyboard=True, one_time_keyboard=True,
        ),
    )


def _build_weather_region_content(state):
    """Build text and InlineKeyboardMarkup for the current weather region step."""
    level = len(state["selected"])
    label = WEATHER_REGION_LABELS[level]
    rows = state.get("search_rows", state["rows"])
    pages = max(1, (len(rows) + WEATHER_PAGE_SIZE - 1) // WEATHER_PAGE_SIZE)
    page = min(max(0, state.get("page", 0)), pages - 1)
    state["page"] = page
    items = rows[page * WEATHER_PAGE_SIZE:(page + 1) * WEATHER_PAGE_SIZE]
    parent = state["selected"][-1]["name"] if state["selected"] else "Indonesia"
    text = f"<b>Pilih {html.escape(label)} · langkah {level + 1}/4</b>\n{html.escape(parent)}\n\n"
    text += "Pilih wilayah dari tombol di bawah."
    text += f"\nHalaman {page + 1}/{pages} · {len(rows)} pilihan"
    text += "\n\nBerlaku 5 menit sejak mulai."
    keyboard = []
    for index in range(0, len(items), 2):
        row_buttons = []
        for item in items[index:index + 2]:
            row_buttons.append(InlineKeyboardButton(item["name"], callback_data=f"wr_sel:{item['code']}"))
        keyboard.append(row_buttons)
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton("← Sebelumnya", callback_data=WEATHER_PREVIOUS))
    if page < pages - 1:
        navigation.append(InlineKeyboardButton("Berikutnya →", callback_data=WEATHER_NEXT))
    if navigation:
        keyboard.append(navigation)
    if "search_rows" in state:
        keyboard.append([InlineKeyboardButton("Semua wilayah", callback_data=WEATHER_ALL)])
    keyboard.append([InlineKeyboardButton("❌ Batal", callback_data=WEATHER_CANCEL)])
    return text, InlineKeyboardMarkup(keyboard)


async def prompt_weather_region(message, state, *, edit=False):
    text, markup = _build_weather_region_content(state)
    if edit:
        await message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        sent = await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        state["menu_message_id"] = sent.message_id


async def weather_manual_command(update, context):
    if not is_allowed(update):
        await deny(update)
        return
    context.user_data.pop("weather_request", None)
    context.user_data.pop("weather_manual", None)
    service = context.application.bot_data["weather_service"]
    try:
        rows = await service.regions(1)
    except WeatherError as error:
        await update.effective_message.reply_text(str(error), reply_markup=ReplyKeyboardRemove())
        return
    state = {"started": time.time(), "selected": [], "rows": rows}
    context.user_data["weather_manual"] = state
    await update.effective_message.reply_text("Memuat daftar provinsi...", reply_markup=ReplyKeyboardRemove())
    await prompt_weather_region(update.effective_message, state)


async def weather_region_callback(update, context):
    """Handle inline button presses for manual weather region selection."""
    query = update.callback_query
    if not is_allowed(update):
        await query.answer("Akses ditolak.", show_alert=True)
        return
    await query.answer()
    state = context.user_data.get("weather_manual")
    if state is None:
        await query.edit_message_text("Sesi cuaca sudah berakhir. Kirim /cuaca_manual untuk mulai lagi.")
        return
    if time.time() - state["started"] > WEATHER_REQUEST_TTL:
        context.user_data.pop("weather_manual", None)
        await query.edit_message_text("Permintaan wilayah kedaluwarsa. Kirim /cuaca_manual lagi.")
        return
    data = query.data
    if data == WEATHER_CANCEL:
        context.user_data.pop("weather_manual", None)
        await query.edit_message_text("Permintaan cuaca dibatalkan.")
        return
    if data == WEATHER_ALL:
        state.pop("search_rows", None)
        state["page"] = 0
        await prompt_weather_region(query.message, state, edit=True)
        return
    if data == WEATHER_NEXT:
        state["page"] = state.get("page", 0) + 1
        await prompt_weather_region(query.message, state, edit=True)
        return
    if data == WEATHER_PREVIOUS:
        state["page"] = max(0, state.get("page", 0) - 1)
        await prompt_weather_region(query.message, state, edit=True)
        return
    if data.startswith("wr_sel:"):
        code = data[len("wr_sel:"):]
        level = len(state["selected"]) + 1
        parent = state["selected"][-1]["code"] if state["selected"] else ""
        # Find the region matching the code
        rows = state.get("search_rows", state["rows"])
        region = next((r for r in rows if r["code"] == code), None)
        if region is None:
            rows_all = state["rows"]
            region = next((r for r in rows_all if r["code"] == code), None)
        if region is None:
            await query.answer("Wilayah tidak ditemukan. Coba lagi.", show_alert=True)
            return
        selected = state["selected"] + [region]
        service = context.application.bot_data["weather_service"]
        if level < 4:
            try:
                next_rows = await service.regions(level + 1, region["code"])
            except WeatherError as error:
                context.user_data.pop("weather_manual", None)
                await query.edit_message_text(str(error))
                return
            state["selected"], state["rows"] = selected, next_rows
            state["page"] = 0
            state.pop("search_rows", None)
            await prompt_weather_region(query.message, state, edit=True)
            return
        # All 4 levels selected — fetch forecast
        context.user_data.pop("weather_manual", None)
        await query.edit_message_text("Mengambil prakiraan BMKG untuk wilayah pilihan...")
        try:
            if HAS_WEATHER_CARD and generate_weather_card:
                try:
                    forecast_obj = await service.forecast_for_regions(selected, structured=True)
                except TypeError:
                    forecast_obj = await service.forecast_for_regions(selected)
                card_buf = generate_weather_card(forecast_obj.data, forecast_obj.code)
                await query.message.reply_photo(
                    photo=card_buf,
                    caption=f"🌦 <b>Prakiraan Cuaca BMKG</b>\n📍 <b>{forecast_obj.location.get('desa')}, {forecast_obj.location.get('kecamatan')}</b>\n{forecast_obj.location.get('kotkab')}, {forecast_obj.location.get('provinsi')}",
                    parse_mode=ParseMode.HTML,
                )
                try:
                    await query.message.delete()
                except TelegramError:
                    pass
                return
            else:
                text = await service.forecast_for_regions(selected)
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                return
        except WeatherError as error:
            text = html.escape(str(error))
        except Exception as error:
            logger.warning("Manual weather request failed (%s)", type(error).__name__)
            text = "Prakiraan gagal diproses. Kirim /cuaca_manual lagi nanti."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def handle_weather_region_text(update, context):
    """Placeholder kept for compatibility; inline buttons replaced text input."""
    message = update.effective_message
    await message.reply_text(
        "Pilih wilayah menggunakan tombol di menu cuaca di atas. "
        "Jika menu sudah hilang, kirim /cuaca_manual untuk memulai lagi."
    )


async def cancel_weather(update, context):
    if not is_allowed(update):
        await deny(update)
        return
    context.user_data.pop("weather_request", None)
    state = context.user_data.pop("weather_manual", None)
    if state and "menu_message_id" in state:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=state["menu_message_id"],
                text="Permintaan cuaca dibatalkan.",
            )
        except TelegramError:
            pass
    await update.effective_message.reply_text("Permintaan cuaca dibatalkan.", reply_markup=ReplyKeyboardRemove())


async def handle_weather_location(update, context):
    if not is_allowed(update):
        await deny(update)
        return
    # Edited/live updates cannot fulfill a new request using an old location message.
    if not update.message:
        return
    message = update.effective_message
    if "weather_manual" in context.user_data:
        await message.reply_text("Anda sedang mengisi wilayah manual. Ketik nama wilayah yang diminta, atau /cuaca untuk memakai GPS.")
        return
    requested = context.user_data.pop("weather_request", None)
    if requested is None or time.time() - requested > WEATHER_REQUEST_TTL:
        await message.reply_text("Kirim /cuaca terlebih dahulu, lalu bagikan lokasi baru.", reply_markup=ReplyKeyboardRemove())
        return
    if message.date.timestamp() < int(requested):
        await message.reply_text("Gunakan /cuaca lagi dan kirim lokasi statis yang baru, bukan live location.", reply_markup=ReplyKeyboardRemove())
        return
    try:
        location = coordinates_from_message(message)
    except WeatherError as error:
        await message.reply_text(str(error) + " Kirim /cuaca untuk mencoba lagi.", reply_markup=ReplyKeyboardRemove())
        return
    status = await message.reply_text("Mencocokkan wilayah dan mengambil prakiraan BMKG...", reply_markup=ReplyKeyboardRemove())
    try:
        if HAS_WEATHER_CARD and generate_weather_card:
            try:
                forecast_obj = await context.application.bot_data["weather_service"].forecast(
                    location.latitude, location.longitude, structured=True,
                )
            except TypeError:
                forecast_obj = await context.application.bot_data["weather_service"].forecast(
                    location.latitude, location.longitude,
                )
            card_buf = generate_weather_card(forecast_obj.data, forecast_obj.code)
            await message.reply_photo(
                photo=card_buf,
                caption=f"🌦 <b>Prakiraan Cuaca BMKG</b>\n📍 <b>{forecast_obj.location.get('desa')}, {forecast_obj.location.get('kecamatan')}</b>\n{forecast_obj.location.get('kotkab')}, {forecast_obj.location.get('provinsi')}",
                parse_mode=ParseMode.HTML,
            )
            try:
                await status.delete()
            except TelegramError:
                pass
            return
        else:
            text = await context.application.bot_data["weather_service"].forecast(
                location.latitude, location.longitude,
            )
    except RegionSelectionRequired as error:
        state = {"started": time.time(), "selected": error.selected, "rows": error.candidates}
        context.user_data["weather_manual"] = state
        try:
            await status.edit_text("Lokasi berhasil dibaca. Data peta belum lengkap/cocok; pilih wilayah berikut agar prakiraan tepat.")
        except TelegramError:
            logger.warning("Could not update weather status message")
        await prompt_weather_region(message, state)
        return
    except WeatherError as error:
        text = html.escape(str(error))
    except Exception as error:
        # Do not log exceptions/tracebacks containing geocoder URLs or coordinates.
        logger.warning("Weather request failed (%s)", type(error).__name__)
        text = "Prakiraan gagal diproses. Kirim /cuaca lagi nanti."
    # Status carries ReplyKeyboardRemove; send a new message rather than editing it.
    await message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    try:
        await status.delete()
    except TelegramError:
        logger.warning("Could not remove weather status message")


async def show_menu(update, context, section):
    if not is_allowed(update):
        if update.callback_query:
            await update.callback_query.answer("Akses ditolak.", show_alert=True)
        else:
            await deny(update)
        return
    pending_location = context.user_data.pop("weather_request", None)
    pending_manual = context.user_data.pop("weather_manual", None)
    if pending_location is not None or pending_manual is not None:
        await update.effective_message.reply_text("Permintaan lokasi dibatalkan.")
    context.user_data["menu"] = section
    text, keyboard = menu_content(section)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    await context.bot.set_my_commands(menu_commands(section), scope=BotCommandScopeChat(chat_id=ALLOWED_USER_ID))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return

    doc = update.effective_message.document
    if not doc:
        return

    file_name = doc.file_name or "document"
    ext = os.path.splitext(file_name)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        await update.effective_message.reply_text(
            f"⚠️ Format file <code>{ext}</code> belum didukung untuk konversi.\n\n"
            "Format yang didukung: <b>PDF, DOCX, XLSX, PPTX, JPG, PNG</b>.",
            parse_mode=ParseMode.HTML,
        )
        return

    file_id = doc.file_id
    options = SUPPORTED_EXTENSIONS[ext]

    context.user_data[f"file_{file_id}"] = {
        "file_id": file_id,
        "file_name": file_name,
        "ext": ext,
    }

    labels = {
        "docx": "📝 Word (.docx)",
        "xlsx": "📊 Excel (.xlsx)",
        "pptx": "📽️ PowerPoint (.pptx)",
        "images": "🖼️ Ekstrak Gambar",
        "pdf": "📄 Convert to PDF",
    }

    buttons = [
        [InlineKeyboardButton(labels.get(target, target.upper()), callback_data=f"convert:{file_id}:{target}")]
        for target in options
    ]

    await update.effective_message.reply_text(
        f"📄 <b>File Diterima:</b> <code>{file_name}</code>\n"
        f"Ukuran: {round(doc.file_size / 1024, 1)} KB\n\n"
        "Pilih format tujuan konversi di bawah ini:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML,
    )


async def handle_photo_conversion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await deny(update)
        return

    photos = update.effective_message.photo
    if not photos:
        return

    photo = photos[-1]
    file_id = photo.file_id

    context.user_data[f"file_{file_id}"] = {
        "file_id": file_id,
        "file_name": f"image_{file_id[:8]}.jpg",
        "ext": ".jpg",
    }

    buttons = [
        [InlineKeyboardButton("📄 Convert Foto ke PDF", callback_data=f"convert:{file_id}:pdf")]
    ]

    await update.effective_message.reply_text(
        "🖼️ <b>Foto Diterima!</b> Ingin jadikan file PDF?",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML,
    )


async def convert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":", 2)
    if len(parts) != 3:
        return

    _, file_id, target = parts
    file_info = context.user_data.get(f"file_{file_id}")
    if not file_info:
        await query.edit_message_text("⚠️ Sesi konversi sudah kedaluwarsa. Silakan kirim file lagi.")
        return

    status = await query.edit_message_text(f"⏳ Sedang mengonversi ke <b>{target.upper()}</b>...", parse_mode=ParseMode.HTML)

    workspace = new_workspace()
    input_file_path = os.path.join(workspace, file_info["file_name"])
    try:
        tg_file = await context.bot.get_file(file_id)
        await tg_file.download_to_drive(input_file_path)

        base_stem = Path(file_info["file_name"]).stem
        ext = file_info["ext"]

        async def deliver(path: str, caption: str) -> None:
            """Send a produced file, always closing the handle afterwards.

            Leaving the handle open blocks deletion on Windows, which is how
            workspace directories end up stranded on disk.
            """
            with open(path, "rb") as document:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=document,
                    caption=caption,
                )

        if ext == ".pdf":
            if target == "docx":
                out_path = os.path.join(workspace, f"{base_stem}.docx")
                await asyncio.to_thread(convert_pdf_to_docx, input_file_path, out_path)
                await deliver(out_path, "✅ Berhasil dikonversi ke Word (.docx)")
            elif target == "xlsx":
                out_path = os.path.join(workspace, f"{base_stem}.xlsx")
                await asyncio.to_thread(convert_pdf_to_xlsx, input_file_path, out_path)
                await deliver(out_path, "✅ Berhasil diekstrak ke Excel (.xlsx)")
            elif target == "pptx":
                out_path = os.path.join(workspace, f"{base_stem}.pptx")
                await asyncio.to_thread(convert_pdf_to_pptx, input_file_path, out_path)
                await deliver(out_path, "✅ Berhasil dikonversi ke PowerPoint (.pptx)")
            elif target == "images":
                images = await asyncio.to_thread(convert_pdf_to_images, input_file_path, workspace)
                for image_path in images[:10]:
                    await deliver(image_path, "🖼️ Halaman hasil render")
        elif ext in [".jpg", ".jpeg", ".png"]:
            out_path = os.path.join(workspace, f"{base_stem}.pdf")
            await asyncio.to_thread(convert_image_to_pdf, input_file_path, out_path)
            await deliver(out_path, "✅ Berhasil dikonversi ke PDF")
        elif ext in [".docx", ".xlsx", ".pptx"]:
            out_path = await asyncio.to_thread(convert_office_to_pdf, input_file_path, workspace)
            await deliver(out_path, "✅ Berhasil dikonversi ke PDF")

        await status.delete()
    except Exception as err:
        logger.error("Conversion failed: %s", err, exc_info=True)
        await status.edit_text(f"❌ Gagal melakukan konversi: {html.escape(str(err))}")
    finally:
        # Drop the session entry so repeated uploads do not accumulate.
        context.user_data.pop(f"file_{file_id}", None)
        # The produced file has already been delivered; nothing needs to survive.
        shutil.rmtree(workspace, ignore_errors=True)


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
                "export": export_command, "storage": storage_command, "cuaca": weather_command,
                "cuaca_manual": weather_manual_command}
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
    if "weather_manual" in context.user_data:
        await handle_weather_region_text(update, context)
        return
    if text == WEATHER_MANUAL_LABEL:
        await weather_manual_command(update, context)
        return
    
     
    is_tiktok = is_tiktok_url(text)
    is_youtube = is_youtube_url(text)
    is_instagram = is_instagram_url(text)
    
    if not is_tiktok and not is_youtube and not is_instagram:
        requested = context.user_data.get("weather_request")
        if requested is not None:
            if time.time() - requested > WEATHER_REQUEST_TTL:
                context.user_data.pop("weather_request", None)
                await message.reply_text("Permintaan lokasi kedaluwarsa. Kirim /cuaca lagi.", reply_markup=ReplyKeyboardRemove())
            else:
                await message.reply_text("Gunakan tombol Kirim lokasi saya atau Lampiran → Lokasi. /batal untuk membatalkan.")
            return
        await message.reply_text(
            "❌ <b>URL tidak valid</b>\n\n"
            "Silakan kirim link TikTok, YouTube, atau Instagram yang dapat diakses secara publik.",
            parse_mode=ParseMode.HTML,
        )
        return

    platform = "TikTok" if is_tiktok else ("YouTube" if is_youtube else "Instagram")
    request_id = uuid4().hex[:12]
    pending = context.user_data.setdefault("downloads", {})
    if len(pending) >= 20:
        pending.pop(next(iter(pending)))
    pending[request_id] = (text, platform)
    
    # Instagram doesn't need quality selection
    if is_instagram:
        await message.reply_text(
            f"📷 <b>Media Instagram diterima</b>\n\n"
            "Tekan Lanjutkan untuk mengunduh foto atau video. Untuk carousel, hanya item pertama yang diunduh.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Lanjutkan", callback_data=f"quality:normal:{request_id}")]
            ]),
        )
    else:
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
            await status.edit_text(f"Mengunduh media {platform}...\nMengambil media dan menyiapkan file.")
            logger.info("User %s requested %s download", user_id, platform)
            if platform == "YouTube":
                try:
                    file_path = await asyncio.to_thread(download_youtube, url, quality)
                except Exception as yt_error:
                    if is_local_file_error(yt_error):
                        raise
                    logger.error("YouTube download failed for user %s: %s", user_id, yt_error)
                    raise DownloadError("YouTube download failed") from yt_error
            elif platform == "Instagram":
                try:
                    file_path = await asyncio.to_thread(download_instagram, url)
                except Exception as ig_error:
                    if is_local_file_error(ig_error):
                        raise
                    logger.error("Instagram download failed for user %s: %s", user_id, ig_error)
                    raise DownloadError(str(ig_error)) from ig_error
            else:  # TikTok
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
                "⚠️ <b>Media terlalu besar</b>\n\n"
                "Media berhasil diunduh, tetapi ukurannya melebihi batas Telegram.\n"
                "Silakan pilih media yang lebih kecil.",
                parse_mode=ParseMode.HTML,
            )
            return

        await status.edit_text(
            f"✅ <b>Download selesai</b>\nUkuran: {file_path.stat().st_size / (1024 * 1024):.1f} MB\n\n📤 Mengirim ke Telegram...",
            parse_mode=ParseMode.HTML,
        )
        logger.info("Upload started for user %s", user_id)
        
        # Determine media type and send accordingly
        if file_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            # Send as photo if it's an Instagram photo
            with file_path.open("rb") as media:
                await message.reply_photo(
                    photo=media,
                    caption="🎉 <b>Media berhasil dikirim!</b>",
                    parse_mode=ParseMode.HTML,
                )
        else:
            # Send as video
            with file_path.open("rb") as media:
                await message.reply_video(
                    video=media,
                    caption="🎉 <b>Media berhasil dikirim!</b>",
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
    except DownloadError as error:
        logger.exception("Download failed for user %s", user_id)
        try:
            await status.edit_text(
                ("❌ <b>Download Instagram gagal</b>\n\n" + html.escape(str(error))
                 if platform == "Instagram" else build_download_failure(platform)),
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
    # Remove conversion workspaces stranded by an earlier crash. Scoped to our
    # own directory and to entries older than the stale threshold, so a
    # concurrent instance's in-flight conversion is never touched.
    cleanup_stale_workspaces()
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
    application.bot_data["weather_service"] = WeatherService(WEATHER_GEOCODER_URL)
    application.bot_data["discord_monitor"] = DiscordVoiceMonitor(store, DISCORD_GUILD_ID)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler(["downloader", "discord", "cuaca", "converter"], category_command))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:(home|downloader|discord|cuaca|converter)$"))
    application.add_handler(CallbackQueryHandler(action_callback, pattern=r"^action:(stats|today|history|export|storage|cuaca|cuaca_manual)$"))
    application.add_handler(CallbackQueryHandler(convert_callback, pattern=r"^convert:"))
    application.add_handler(CallbackQueryHandler(weather_region_callback, pattern=r"^wr_"))
    application.add_handler(CommandHandler("cuaca", weather_command))
    application.add_handler(CommandHandler("cuaca_manual", weather_manual_command))
    application.add_handler(CommandHandler("batal", cancel_weather))
    application.add_handler(MessageHandler(WEATHER_LOCATION_FILTER, handle_weather_location))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_conversion))
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
