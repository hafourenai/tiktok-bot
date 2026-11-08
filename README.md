# 🍽️ Bot Menu - Telegram Menu Image Generator

Sistem otomatis untuk generate gambar menu dari Google Sheets dan mengirimnya ke Telegram ketika ada request.

## 📋 Fitur

✅ **Auto-fetch data** dari Google Sheets CSV  
✅ **Filter stok** - Hanya tampilkan item dengan stok > 0 dan status aktif  
✅ **Gambar menarik** - Desain menu dengan kategori berwarna dan typography yang legible  
✅ **Telegram Bot** - Respond ke keyword "menu nya apa saja?" dan variasi lainnya  
✅ **Polling otomatis** - Check perubahan stok setiap 5 menit (dapat dikonfigurasi)  
✅ **Smart cache** - Hanya regenerate gambar jika ada perubahan stok  

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Clone atau buka folder project
cd bot_honey

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup Telegram Bot Token

```bash
# Copy .env.example ke .env
cp .env.example .env

# Edit .env dan masukkan token Telegram (dapatkan dari @BotFather)
TELEGRAM_TOKEN=your_actual_token_here
```

### 3. Generate Menu Pertama Kali

```bash
python generate_menu.py
```

Gambar menu akan disimpan di `public/menu.png`

### 4. Jalankan Bot

**Terminal 1 - Bot Telegram:**
```bash
python bot_telegram.py
```

**Terminal 2 (Opsional) - Polling Service:**
```bash
python check_stok_changes.py
```

Polling service akan check perubahan stok setiap 5 menit dan otomatis regenerate gambar jika ada perubahan.

---

## 📁 Struktur Folder

```
bot_honey/
├── config.py                 # Konfigurasi (kategori, warna, dll)
├── generate_menu.py          # Script generate gambar menu
├── bot_telegram.py           # Telegram bot
├── check_stok_changes.py     # Polling service untuk auto-update
├── requirements.txt          # Dependencies
├── .env.example              # Template environment variables
├── .env                      # Environment variables (jangan commit!)
├── public/
│   └── menu.png              # Output gambar menu (auto-generated)
└── cache/
    └── menu_cache.json       # Cache untuk track perubahan
```

---

## 🎨 Customization

### Mengubah Kategori & Warna

Edit di `config.py`:

```python
KATEGORI_MAP = {
    "SAT_": "🍖 Lauk Satuan",
    "ASIN_": "🐟 Ikan Asin & Lauk Tambahan",
    # ... tambah atau edit sesuai kebutuhan
}

KATEGORI_COLOR = {
    "🍖 Lauk Satuan": "#FF6B6B",  # Merah
    "🐟 Ikan Asin & Lauk Tambahan": "#4ECDC4",  # Biru Muda
    # ... ubah color hex sesuai selera
}
```

### Mengubah Polling Interval

Edit di `config.py`:

```python
POLLING_INTERVAL = 300  # Ubah ke berapa detik (default 5 menit = 300 detik)
```

### Mengubah Keyword Bot

Edit di `bot_telegram.py` di fungsi `handle_message()`:

```python
menu_keywords = [
    "menu nya apa saja",
    "menu apa saja",
    "apa menu",
    # ... tambah keyword lain
]
```

---

## 📊 Workflow

### Generate Menu Image

```
fetch CSV → filter stok > 0 & aktif → group by kategori → 
→ generate gambar dengan PIL → save ke public/menu.png → cache hash
```

### Telegram Bot

```
user: "menu nya apa saja?"
     ↓
bot mendeteksi keyword
     ↓
check apakah menu.png ada
     ↓
kirim gambar ke user
```

### Polling Service

```
every 5 minutes:
  - fetch CSV terbaru
  - bandingkan hash dengan cache
  - jika berbeda → regenerate gambar
  - update cache
```

---

## 🔧 Commands Bot

| Command | Fungsi |
|---------|--------|
| `/start` | Tampilkan pesan sambutan |
| `/help` | Tampilkan bantuan |
| `/menu` | Tampilkan gambar menu |

Atau cukup ketik salah satu keyword:
- "menu nya apa saja?"
- "menu apa saja?"
- "apa menu?"
- "menu hari ini?"
- "menu"

---

## 📝 Logs & Debugging

### Generate Menu
```
✓ Data fetched. Total items: 57
✓ Filtered items (stok > 0 & aktif = TRUE): 55
✓ Stok changes detected!
✓ Menu image saved: public/menu.png
✓ Menu generation completed successfully!
```

### Bot Running
```
🤖 Bot is running...
Press Ctrl+C to stop the bot
```

### Polling Service
```
[Poll #1] 08/11/2026 23:30:00
Checking for stok changes...
✓ Data fetched. Total items: 57
ℹ No changes detected. Skipping image regeneration.
Next poll in 300 seconds...
```

---

## ⚠️ Troubleshooting

### Error: "TELEGRAM_TOKEN not set"
→ Pastikan `.env` sudah dibuat dan berisi `TELEGRAM_TOKEN` yang valid

### Menu image tidak tampil
→ Pastikan folder `public/` ada, atau buat manual dengan `mkdir public`

### Polling tidak berjalan
→ Jalankan `check_stok_changes.py` di terminal terpisah

### Gambar pixelated atau kecil
→ Ubah `IMAGE_CONFIG['dpi']` atau `figsize` di `config.py`

---

## 📌 Notes

- Google Sheets harus **Published to the web** agar CSV URL bisa diakses
- Token Telegram harus **valid** dan bot harus **sudah dimulai** (user kirim `/start`)
- Polling service berjalan independent dari bot, bisa dijalankan di server terpisah
- Cache tersimpan di `cache/menu_cache.json` untuk detect perubahan

---

## 🎯 Next Steps (Webhook)

Saat ini menggunakan **polling** (5 menit sekali check). Nanti bisa upgrade ke **webhook** agar lebih real-time:

1. Setup Google Sheets trigger via **Google Apps Script**
2. Webhook panggil endpoint bot ketika ada perubahan stok
3. Bot immediate regenerate gambar tanpa menunggu polling interval

---

Happy coding! 🚀
