import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN belum diatur di .env")

try:
    ALLOWED_USER_ID = int(os.getenv("ALLOWED_TELEGRAM_USER_ID", "0"))
    MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "50"))
except ValueError as error:
    raise RuntimeError("ALLOWED_TELEGRAM_USER_ID dan MAX_FILE_SIZE_MB harus valid") from error

if ALLOWED_USER_ID <= 0:
    raise RuntimeError("ALLOWED_TELEGRAM_USER_ID belum diatur di .env")

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
MAX_FILE_SIZE_BYTES = int(MAX_FILE_SIZE_MB * 1024 * 1024)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
DISCORD_GUILD_ID_RAW = os.getenv("DISCORD_GUILD_ID", "").strip()
try:
    DISCORD_GUILD_ID = int(DISCORD_GUILD_ID_RAW) if DISCORD_GUILD_ID_RAW else None
except ValueError as error:
    raise RuntimeError("DISCORD_GUILD_ID harus berupa angka") from error

TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta").strip()
try:
    ZoneInfo(TIMEZONE)
except ZoneInfoNotFoundError as error:
    raise RuntimeError("TIMEZONE tidak valid") from error
VOICE_DATABASE_PATH = Path(os.getenv("VOICE_DATABASE_PATH", "data/voice_stats.db"))
VOICE_EXPORT_DIR = Path(os.getenv("VOICE_EXPORT_DIR", "data/exports"))

TIKTOK_FALLBACK_URL = os.getenv("TIKTOK_FALLBACK_URL", "https://snaptikhon.vercel.app/").strip()

TIKTOK_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:tiktok\.com/@[^/\s]+/video/\d+|(?:vm|vt)\.tiktok\.com/[A-Za-z0-9]+/?)(?:\?.*)?$",
    re.IGNORECASE,
)

YOUTUBE_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:youtube\.com/watch\?(?:.*&)?v=[-\w]{11}.*|youtu\.be/[-\w]{11}(?:\?.*)?|youtube\.com/embed/[-\w]{11}(?:\?.*)?)$",
    re.IGNORECASE,
)
