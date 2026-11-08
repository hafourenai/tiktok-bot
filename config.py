import os
from dotenv import load_dotenv

load_dotenv()

# Google Sheets CSV URL
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRPYK4IWDOYb3qACH2dZb1MRI8vC3Dx2G6BADd5LbORAiF1wVyT7_69q7VsghdHiswxjpK_A8PHPMcl/pub?output=csv"

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your_token_here")

# Folder untuk menyimpan gambar dan cache
PUBLIC_DIR = "public"
CACHE_DIR = "cache"

# Kategori mapping
KATEGORI_MAP = {
    "SAT_": "🍖 Lauk Satuan",
    "ASIN_": "🐟 Ikan Asin & Lauk Tambahan",
    "SAY_": "🥬 Sayuran",
    "PEL_": "🌶️ Pelengkap",
    "MIN_": "🥤 Minuman",
    "KEM_": "📦 Kemasan",
    "REG_": "🍚 Paket Reguler",
    "KEL_": "👨‍👩‍👧‍👦 Paket Sekeluarga",
    "RAM_": "🌙 Paket Ramadhan",
    "JUK_": "🍲 Paket Combo Jukut",
    "TEH_": "🧋 Paket Es Teh Manis",
    "JER_": "🧃 Paket Es Jeruk",
}

# Warna untuk kategori (RGB)
KATEGORI_COLOR = {
    "🍖 Lauk Satuan": "#FF6B6B",
    "🐟 Ikan Asin & Lauk Tambahan": "#4ECDC4",
    "🥬 Sayuran": "#95E1D3",
    "🌶️ Pelengkap": "#FFA502",
    "🥤 Minuman": "#00B4D8",
    "📦 Kemasan": "#C7B3E5",
    "🍚 Paket Reguler": "#FFB703",
    "👨‍👩‍👧‍👦 Paket Sekeluarga": "#FB5607",
    "🌙 Paket Ramadhan": "#8338EC",
    "🍲 Paket Combo Jukut": "#FFBE0B",
    "🧋 Paket Es Teh Manis": "#52B788",
    "🧃 Paket Es Jeruk": "#06FFA5",
}

# Konfigurasi gambar
IMAGE_CONFIG = {
    "dpi": 150,
    "figsize": (10, 14),
    "bg_color": "#F8F9FA",
    "header_bg": "#2C3E50",
    "header_text": "#FFFFFF",
    "row_height": 0.08,
    "font_size_title": 24,
    "font_size_category": 14,
    "font_size_item": 11,
    "font_size_small": 9,
}

# Polling interval (dalam detik)
POLLING_INTERVAL = 300  # 5 menit

# Nama file output
MENU_IMAGE = "menu.png"
MENU_CACHE = "menu_cache.json"
