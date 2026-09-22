# Telegram Video Downloader Bot

Bot Telegram pribadi untuk mengunduh video TikTok dan YouTube publik serta mengirimkannya kembali kepada satu Telegram user yang diizinkan.

Bot meminta pilihan kualitas **Biasa** atau **HD**, menghapus file sementara setelah selesai, dan membatasi download bersamaan agar cocok untuk Termux.

## Fitur

- `/start` dan `/help`
- Validasi link TikTok: `tiktok.com`, `vm.tiktok.com`, `vt.tiktok.com`
- Validasi link YouTube: `youtube.com`, `youtu.be`
- Pilihan kualitas Biasa atau HD
- Batas maksimal dua download bersamaan
- Batas ukuran file sebelum upload
- Cleanup file sementara setelah proses dan saat startup
- Allowlist satu Telegram user ID
- Fallback downloader TikTok: `yt-dlp`, `gallery-dl`, lalu package Node.js `@tobyg74/tiktok-api-dl`
- YouTube downloader: `yt-dlp` dengan library `youtube-api-dl` opsional

## Batasan Dan Keamanan

- Hanya gunakan untuk video TikTok dan YouTube yang dapat diakses publik.
- Bot tidak menggunakan login, cookies, DRM, paywall, atau bypass access control.
- Fallback `tiktok-api-dl` memakai layanan tidak resmi dan dapat berhenti bekerja tanpa pemberitahuan.
- YouTube downloader menggunakan `yt-dlp` yang stabil dan actively maintained.
- Jangan pernah commit `.env`, token Telegram, cookies, atau file hasil download.
- Token yang pernah dibagikan harus segera direvoke melalui `@BotFather`.

## Requirements

- Android
- Termux dari F-Droid atau repository resmi Termux
- Python 3.10 atau lebih baru
- Node.js dan NPM
- FFmpeg
- Token Telegram Bot
- Telegram user ID pemilik bot

## Instalasi Termux: Step By Step

### 1. Update Termux

Buka Termux, lalu jalankan:

```bash
pkg update
pkg upgrade
```

Tekan `Y` jika Termux meminta konfirmasi.

### 2. Install program yang diperlukan

```bash
pkg install python nodejs-lts ffmpeg git
```

Jika `nodejs-lts` tidak tersedia pada repository Termux kamu, gunakan:

```bash
pkg install python nodejs ffmpeg git
```

### 3. Periksa versi program

```bash
python --version
node --version
npm --version
ffmpeg -version
```

Python harus versi 3.10 atau lebih baru.

### 4. Ambil project

Ganti URL berikut dengan URL repository GitHub kamu:

```bash
git clone https://github.com/hafourenai/tiktok-bot.git
cd tiktok-bot
```

Jika project sudah ada di storage Termux, cukup masuk ke folder project:

```bash
cd ~/tiktok-bot
```

### 5. Buat Python virtual environment

```bash
python -m venv venv
source venv/bin/activate
```

Jika berhasil, biasanya prompt Termux berubah dan menampilkan `(venv)`.

### 6. Install dependency Python

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 7. Install dependency Node.js

```bash
npm install
```

Perintah ini membaca `package.json` dan memasang `@tobyg74/tiktok-api-dl` ke folder `node_modules/`.

### 8. Buat file konfigurasi

```bash
cp .env.example .env
nano .env
```

Isi `.env` seperti berikut:

```env
TELEGRAM_BOT_TOKEN=TOKEN_BOT_BARU_DARI_BOTFATHER
ALLOWED_TELEGRAM_USER_ID=123456789
DOWNLOAD_DIR=downloads
MAX_FILE_SIZE_MB=50
```

Keterangan:

- `TELEGRAM_BOT_TOKEN`: token dari `@BotFather`.
- `ALLOWED_TELEGRAM_USER_ID`: Telegram user ID yang boleh menggunakan bot.
- `DOWNLOAD_DIR`: folder temporary download.
- `MAX_FILE_SIZE_MB`: batas ukuran file sebelum upload.

Simpan di nano dengan `Ctrl+O`, tekan `Enter`, lalu keluar dengan `Ctrl+X`.

### 9. Jalankan unit test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

### 10. Jalankan bot

```bash
python bot.py
```

Jika berhasil, log akan menampilkan:

```text
INFO Bot started
```

Biarkan sesi Termux tetap berjalan selama bot digunakan.

## Pengujian Telegram

1. Kirim `/start` dari akun yang ID-nya ada di `.env`.
2. Kirim `/help`.
3. Kirim link TikTok panjang atau short link, misalnya `https://vt.tiktok.com/...`.
4. Atau kirim link YouTube, misalnya `https://youtu.be/...`.
5. Pilih `Biasa` atau `HD`.
6. Tunggu bot mengirim video.
7. Periksa folder `downloads/`; file temporary seharusnya terhapus.
8. Kirim `/start` dari akun lain untuk memastikan akses ditolak.

## Update Dependency

Aktifkan virtual environment terlebih dahulu:

```bash
source venv/bin/activate
```

Update Python dependency:

```bash
python -m pip install --upgrade -r requirements.txt
```

Update dependency Node.js:

```bash
npm update
```

## Menjalankan Kembali Setelah Termux Ditutup

```bash
cd ~/tiktok-bot
source venv/bin/activate
python bot.py
```

Untuk mencegah Android mematikan proses karena sleep:

```bash
termux-wake-lock
python bot.py
```

Pasang add-on Termux:API hanya jika perintah `termux-wake-lock` belum tersedia.

## Troubleshooting

### `python: command not found`

Install Python:

```bash
pkg install python
```

### `node: command not found`

Install Node.js:

```bash
pkg install nodejs-lts
```

### `ffmpeg: command not found`

```bash
pkg install ffmpeg
```

### Token atau user ID error

Periksa `.env`, pastikan tidak ada spasi tambahan, lalu jalankan ulang bot. Jangan menampilkan isi `.env` di chat atau issue GitHub.

### Download TikTok gagal

Extractor TikTok dapat berubah atau diblokir. Pastikan link publik, coba link lain, update dependency, dan periksa log. Fallback tidak menjamin semua video dapat diunduh.

### Upload Telegram timeout

Coba kualitas `Biasa`, gunakan jaringan yang stabil, atau turunkan `MAX_FILE_SIZE_MB`.

## Struktur Project

```text
bot_honey/
├── bot.py
├── config.py
├── downloader.py
├── tiktok_api_bridge.js
├── youtube_api_dl.js
├── youtube_api_bridge.js
├── requirements.txt
├── package.json
├── package-lock.json
├── .env.example
├── .gitignore
├── downloads/
│   └── .gitkeep
├── tests/
│   ├── test_bot.py
│   └── test_youtube.py
└── README.md
```

## YouTube API Library (`youtube-api-dl`)

### Penggunaan dalam Node.js

```javascript
const { Downloader } = require("./youtube_api_dl");

const response = await Downloader("https://youtu.be/dQw4w9WgXcQ", { version: "v1" });

if (response.status === "success") {
  console.log(response.result.video.url);
  console.log(response.result.meta.title);
  console.log(response.result.formats);
}
```

### CLI Bridge

```bash
node youtube_api_bridge.js <url> [version]
```

Contoh:
```bash
node youtube_api_bridge.js "https://youtu.be/dQw4w9WgXcQ" "v1"
```

Output JSON:
```json
{
  "status": "success",
  "version": "v1",
  "result": {
    "meta": {
      "id": "dQw4w9WgXcQ",
      "title": "Rick Astley - Never Gonna Give You Up",
      "duration": 233,
      "thumbnail": "https://...",
      "channel": "Rick Astley"
    },
    "video": {
      "url": "https://...direct_video_url...",
      "quality": "720p",
      "format": "mp4",
      "sizeBytes": 12345678
    },
    "formats": [...]
  }
}
```

### Format Selection Strategy

- **v1** (Default): Format mp4 gabungan terbaik dengan height ≤ 720p — paling cocok Telegram
- **v2**: Format video terbaik tanpa batas height — untuk kualitas maksimal
- **v3**: Format 360p kecil — untuk file minimal

Jika satu versi gagal, bridge otomatis coba versi berikutnya.
