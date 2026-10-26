# Honey Assistant Bot

Bot Telegram pribadi untuk satu pemilik. Menyediakan pengunduh media publik,
pemantauan voice Discord, prakiraan cuaca BMKG, dan konversi dokumen.

## Fitur

| Layanan | Kemampuan |
| --- | --- |
| Downloader | Unduh media TikTok, YouTube, dan Instagram melalui URL publik. TikTok dan YouTube menawarkan kualitas **Biasa** atau **HD**. |
| TikTok profile | `/stalk <username>` menampilkan ringkasan profil publik TikTok. |
| Discord Voice | Memantau sesi voice, menampilkan statistik dan riwayat, serta membuat export Excel. |
| Cuaca BMKG | Prakiraan hingga tingkat kelurahan/desa lewat lokasi GPS/venue atau pemilihan wilayah manual. |
| Konverter | PDF ke DOCX/XLSX/PPTX/PNG, JPG/PNG ke PDF, serta DOCX/XLSX/PPTX ke PDF. |
| Berita | RSS ANTARA/CNN Indonesia/The Guardian dengan ringkasan AI dan fallback deterministik tanpa AI. |

Bot hanya menerima DM dari `ALLOWED_TELEGRAM_USER_ID`. Download dibatasi dua pekerjaan sekaligus dan berkas sementara dibersihkan setelah diproses.

## Kebutuhan

- Python 3.10 atau lebih baru
- Node.js dan npm
- FFmpeg
- Token bot Telegram dan ID pengguna Telegram pemilik
- Opsional: token bot Discord untuk pemantauan voice

Di Termux, pasang kebutuhan sistem dengan:

```sh
pkg update
pkg install python nodejs-lts ffmpeg git
```

Gunakan `nodejs` bila paket `nodejs-lts` tidak tersedia.

## Instalasi dan menjalankan

```sh
git clone <URL-REPOSITORY> bot_honey
cd bot_honey
python -m venv venv
```

Aktifkan environment:

```sh
# Termux/Linux/macOS
source venv/bin/activate

# Windows PowerShell
.\venv\Scripts\Activate.ps1
```

Pasang dependency dan buat konfigurasi:

```sh
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
npm install
cp .env.example .env
```

Di Windows PowerShell, gunakan `Copy-Item .env.example .env` sebagai pengganti `cp`.
Isi nilai wajib di `.env`, lalu jalankan:

```sh
python bot.py
```

## Konfigurasi

| Variabel | Wajib | Keterangan |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Ya | Token dari @BotFather. |
| `ALLOWED_TELEGRAM_USER_ID` | Ya | ID numerik akun Telegram yang boleh memakai bot. |
| `DOWNLOAD_DIR` | Tidak | Direktori berkas sementara; default `downloads`. |
| `MAX_FILE_SIZE_MB` | Tidak | Batas ukuran media sebelum dikirim; default `50`. |
| `DISCORD_BOT_TOKEN` | Tidak | Mengaktifkan pemantauan voice Discord. |
| `DISCORD_GUILD_ID` | Tidak | ID server Discord yang dipantau; kosong untuk semua server yang dapat diakses bot. |
| `TIMEZONE` | Tidak | Zona waktu laporan voice; default `Asia/Jakarta`. |
| `VOICE_DATABASE_PATH` | Tidak | Lokasi database SQLite; default `data/voice_stats.db`. |
| `VOICE_EXPORT_DIR` | Tidak | Lokasi laporan Excel; default `data/exports`. |
| `WEATHER_GEOCODER_URL` | Tidak | Endpoint Nominatim untuk pemetaan GPS. |
| `INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD` | Untuk Instagram | Akun downloader Instagram; login dapat terkena verifikasi atau rate limit. |
| `TIKTOK_FALLBACK_URL` | Tidak | Halaman unduh alternatif saat semua metode TikTok gagal. |
| `NEWS_SUMMARY_MODE` | Tidak | `auto` (default), `llm`, atau `extractive`. Mode `auto` tetap bekerja saat LLM mati. |
| `NEWS_LLM_BASE_URL` | Tidak | Endpoint lokal llama-server; default `http://127.0.0.1:8080`. |

Jangan commit atau membagikan `.env`, token, kredensial Instagram, maupun hasil unduhan.

## Penggunaan di Telegram

Kirim `/start` atau `/menu`, kemudian pilih layanan. `/help` menampilkan bantuan untuk menu yang sedang aktif.

### Downloader

- Kirim URL TikTok yang didukung (`tiktok.com`, `vm.tiktok.com`, atau `vt.tiktok.com`), URL YouTube (`youtube.com` atau `youtu.be`), atau URL post/reel Instagram.
- Untuk TikTok dan YouTube, pilih **Biasa** atau **HD** setelah URL diterima.
- Instagram mendukung post, reel, dan media story yang sesuai URL; untuk carousel bot mengambil item pertama.
- Jalankan `/stalk <username>` untuk melihat profil TikTok publik.

Gunakan hanya untuk konten publik yang berhak Anda unduh. Bot tidak menangani DRM, paywall, cookies, atau bypass kontrol akses.

### Discord Voice

| Perintah | Fungsi |
| --- | --- |
| `/stats` | Ringkasan seluruh aktivitas. |
| `/today` | Aktivitas hari ini. |
| `/history [hari]` | Riwayat 1–365 hari; default 7 hari. |
| `/export [YYYY-MM]` | Mengirim laporan Excel untuk bulan yang dipilih. |
| `/storage` | Ukuran database dan rentang data. |
| `/delete YYYY-MM` | Menampilkan dampak penghapusan. |
| `/confirm_delete YYYY-MM` | Menghapus data setelah bulan tersebut pernah diekspor. |

Aktifkan **Server Members Intent** pada Discord Developer Portal dan berikan bot akses melihat channel serta voice state. Data disimpan lokal di SQLite. Waktu keluar voice saat bot offline tidak dapat dipulihkan dari Discord.

### Prakiraan Cuaca Indonesia

- Kirim `/cuaca`, lalu bagikan lokasi statis atau venue dari Telegram; live location tidak digunakan.
- Kirim `/cuaca_manual` untuk memilih **provinsi → kota/kabupaten → kecamatan → kelurahan/desa**. Nama juga dapat diketik dan bot akan menawarkan pilihan yang cocok.
- Sesi berlaku lima menit. Gunakan `/batal` untuk membatalkan.
- Nilai prakiraan berasal dari [BMKG](https://data.bmkg.go.id/prakiraan-cuaca/); Nominatim/OpenStreetMap dan [Wilayah.id](https://wilayah.id) hanya digunakan untuk memetakan koordinat ke wilayah.

Koordinat dikirim ke geocoder saat diminta dan tidak disimpan oleh aplikasi. Pemetaan menggunakan objek peta terdekat, bukan verifikasi batas wilayah berbasis poligon; periksa nama wilayah pada hasil, khususnya di perbatasan.

### Konverter dokumen

Kirim dokumen atau foto ke chat, lalu pilih format target yang ditawarkan bot. Hasil dan batasan setiap format ada di [docs/converter.md](docs/converter.md).

### Berita

Gunakan `/berita` untuk berita Indonesia terbaru atau `/berita nasional`,
`/berita internasional`, `/berita teknologi`, `/berita ekonomi`,
`/berita politik`, dan `/berita olahraga`. Jika LLM lokal tidak sehat, bot
langsung memakai ringkasan penerbit atau memilih kalimat faktual dari artikel.
Konfigurasi lengkap tersedia di [NEWS_SKILL_README.md](NEWS_SKILL_README.md).

Untuk hasil Office ke PDF terbaik, instal LibreOffice dan pastikan `soffice` tersedia di `PATH` atau atur `LIBREOFFICE_BIN`. `poppler` diperlukan untuk PDF ke gambar dan `tesseract` diperlukan untuk OCR halaman hasil scan.

## Pemeriksaan dan pengujian

```sh
python check_environment.py
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

`check_environment.py` memeriksa dependency, binary sistem, akses direktori kerja, dan ruang penyimpanan tanpa mencetak token.

## Dokumentasi teknis

- [Konverter dokumen](docs/converter.md): tier konversi, dependency opsional, dan batasan format.
- [BMKG Location Resolver](docs/resolver.md): API package resolver, instalasi mandiri, dan build wheel.

## Struktur penting

```text
bot.py                         # Entry point Telegram bot
config.py                      # Konfigurasi .env
downloader.py                  # Downloader media
discord_voice.py               # Monitor voice Discord
voice_stats.py / voice_export.py
weather.py / weather_card.py   # Integrasi dan kartu cuaca
src/bmkg_location_resolver/    # Package resolver BMKG
src/converter/                 # Mesin konversi dokumen
tests/                         # Pengujian
```
