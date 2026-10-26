import os
import re
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR / path

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

DOWNLOAD_DIR = str(project_path(os.getenv("DOWNLOAD_DIR", "downloads")))
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
VOICE_DATABASE_PATH = project_path(os.getenv("VOICE_DATABASE_PATH", "data/voice_stats.db"))
VOICE_EXPORT_DIR = project_path(os.getenv("VOICE_EXPORT_DIR", "data/exports"))

WEATHER_GEOCODER_URL = os.getenv("WEATHER_GEOCODER_URL", "https://nominatim.openstreetmap.org").strip()

TIKTOK_FALLBACK_URL = os.getenv("TIKTOK_FALLBACK_URL", "https://snaptikhon.vercel.app/").strip()

TIKTOK_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:tiktok\.com/@[^/\s]+/video/\d+|(?:vm|vt)\.tiktok\.com/[A-Za-z0-9]+/?)(?:\?.*)?$",
    re.IGNORECASE,
)

YOUTUBE_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:youtube\.com/watch\?(?:.*&)?v=[-\w]{11}.*|youtu\.be/[-\w]{11}(?:\?.*)?|youtube\.com/embed/[-\w]{11}(?:\?.*)?)$",
    re.IGNORECASE,
)

INSTAGRAM_URL_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories/[A-Za-z0-9_.]+)/[A-Za-z0-9_-]+/?(?:\?[^\s#]*)?(?:#[^\s]*)?$",
    re.IGNORECASE,
)

INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "").strip()
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "").strip()
INSTAGRAM_REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "").strip()
INSTAGRAM_TOKEN_ENCRYPTION_KEY = os.getenv("INSTAGRAM_TOKEN_ENCRYPTION_KEY", "").strip()

# News Skill configuration
NEWS_ENABLED = os.getenv("NEWS_ENABLED", "true").lower() == "true"
NEWS_DB_PATH = project_path(os.getenv("NEWS_DB_PATH", "data/news.db"))
NEWS_MAX_ARTICLES = int(os.getenv("NEWS_MAX_ARTICLES", "5"))
NEWS_CACHE_TTL_SECONDS = int(os.getenv("NEWS_CACHE_TTL_SECONDS", "180"))
NEWS_LOOKBACK_HOURS = int(os.getenv("NEWS_LOOKBACK_HOURS", "48"))
NEWS_HTTP_TIMEOUT_SECONDS = int(os.getenv("NEWS_HTTP_TIMEOUT_SECONDS", "12"))
NEWS_EXTRACT_TIMEOUT_SECONDS = int(os.getenv("NEWS_EXTRACT_TIMEOUT_SECONDS", "15"))

NEWS_LLM_BASE_URL = os.getenv("NEWS_LLM_BASE_URL", "http://127.0.0.1:8080").strip()
NEWS_LLM_MODEL = os.getenv("NEWS_LLM_MODEL", "qwen3-0.6b").strip()
NEWS_LLM_ALLOW_REMOTE = os.getenv("NEWS_LLM_ALLOW_REMOTE", "false").lower() == "true"
NEWS_LLM_TEMPERATURE = float(os.getenv("NEWS_LLM_TEMPERATURE", "0.2"))
NEWS_LLM_MAX_TOKENS = int(os.getenv("NEWS_LLM_MAX_TOKENS", "120"))
NEWS_LLM_TIMEOUT_SECONDS = int(os.getenv("NEWS_LLM_TIMEOUT_SECONDS", "45"))
NEWS_TOTAL_TIMEOUT_SECONDS = int(os.getenv("NEWS_TOTAL_TIMEOUT_SECONDS", "180"))
NEWS_LLM_CONCURRENCY = int(os.getenv("NEWS_LLM_CONCURRENCY", "1"))
NEWS_LLM_CONTEXT_TOKENS = int(os.getenv("NEWS_LLM_CONTEXT_TOKENS", "1024"))
NEWS_LLM_HEALTH_TIMEOUT_SECONDS = float(os.getenv("NEWS_LLM_HEALTH_TIMEOUT_SECONDS", "2"))
NEWS_LLM_COOLDOWN_SECONDS = int(os.getenv("NEWS_LLM_COOLDOWN_SECONDS", "300"))
NEWS_SUMMARY_MODE = os.getenv("NEWS_SUMMARY_MODE", "auto").strip().lower()
NEWS_EXTRACTIVE_MAX_SENTENCES = int(os.getenv("NEWS_EXTRACTIVE_MAX_SENTENCES", "2"))
NEWS_EXTRACTIVE_MAX_WORDS = int(os.getenv("NEWS_EXTRACTIVE_MAX_WORDS", "60"))

if NEWS_SUMMARY_MODE not in {"auto", "llm", "extractive"}:
    raise RuntimeError("NEWS_SUMMARY_MODE harus auto, llm, atau extractive")

# Validate News LLM URL if not remote allowed
if NEWS_ENABLED and not NEWS_LLM_ALLOW_REMOTE:
    parsed_llm_url = urlparse(NEWS_LLM_BASE_URL)
    if parsed_llm_url.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError(
            "NEWS_LLM_BASE_URL must use localhost/127.0.0.1 when NEWS_LLM_ALLOW_REMOTE=false. "
            "Set NEWS_LLM_ALLOW_REMOTE=true to allow remote endpoints."
        )
