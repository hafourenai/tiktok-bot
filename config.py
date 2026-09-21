import os

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
