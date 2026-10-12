# Telegram Video Downloader Bot

## Converter dokumen

Word/Excel/PowerPoint ↔ PDF tersedia melalui menu `/converter`.
Panduan engine, instalasi, dan batasan hasil: [docs/converter.md](docs/converter.md).

## Package resolver cuaca

Resolver kini berada di `src/bmkg_location_resolver/` sebagai package Python
`bmkg-location-resolver` versi 0.1.0. Dokumentasi API dan build:
[docs/resolver.md](docs/resolver.md).

Untuk memperbarui bot, jalankan dari root repository dengan virtual environment aktif:

```sh
python -m pip install -r requirements.txt
python bot.py
```

Untuk menggunakan resolver saja di aplikasi lain: `python -m pip install .` dari
repository ini, atau pasang wheel di `dist/` setelah `python -m build`.
Package **belum diterbitkan ke PyPI**, sehingga `pip install bmkg-location-resolver`
tanpa path belum menjadi metode instalasi yang disediakan project ini.

Share location biasa dan venue didukung oleh adapter terpisah. Jika nama tingkat
administrasi GPS hilang/tidak cocok, bot meneruskan ke pilihan wilayah pada tingkat
tersebut; induk yang sudah cocok tidak perlu diisi ulang. Koordinat tidak disimpan
pada state pilihan. `/batal` membersihkan permintaan seperti alur manual.

Bot Telegram pribadi untuk mengunduh video TikTok dan YouTube publik serta mengirimkannya kembali kepada satu Telegram user yang diizinkan.

Bot meminta pilihan kualitas **Biasa** atau **HD**, menghapus file sementara setelah selesai, dan membatasi download bersamaan agar cocok untuk Termux.

## Fitur

- `/start` atau `/menu` membuka pilihan **Downloader**, **Discord**, dan **Cuaca**.
- `/cuaca` menawarkan input wilayah manual atau lokasi GPS untuk prakiraan resmi BMKG di Indonesia; wilayah dipakai sekali per permintaan.
- Menu command menyesuaikan kategori yang dipilih; `/help` membuka panduan kategori aktif.
- Menu Discord menyediakan tombol statistik, hari ini, riwayat 7 hari, export bulan ini, dan penyimpanan.
- Status download: menunggu slot, mengunduh, mencoba fallback bila diperlukan, mengirim (beserta ukuran file), dan selesai. Status berupa tahapan, bukan persentase.
- Setiap pilihan kualitas terikat pada link masing-masing, sehingga beberapa link tidak saling menimpa.

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
- Discord Bot Token (untuk monitoring Voice Channel)

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
DISCORD_BOT_TOKEN=TOKEN_DISCORD_BOT
DISCORD_GUILD_ID=123456789012345678
TIMEZONE=Asia/Jakarta
```

Keterangan:

- `TELEGRAM_BOT_TOKEN`: token dari `@BotFather`.
- `ALLOWED_TELEGRAM_USER_ID`: Telegram user ID yang boleh menggunakan bot.
- `DOWNLOAD_DIR`: folder temporary download.
- `MAX_FILE_SIZE_MB`: batas ukuran file sebelum upload.
- `DISCORD_BOT_TOKEN`: token bot Discord untuk monitoring voice. Jika kosong, downloader Telegram tetap berjalan, tetapi monitoring Discord dinonaktifkan.
- `DISCORD_GUILD_ID`: ID server Discord yang dipantau. Kosongkan hanya jika bot perlu memantau semua server yang dapat diaksesnya.
- `TIMEZONE`: zona waktu tampilan statistik, default `Asia/Jakarta`.

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

## Prakiraan Cuaca Indonesia

### Input nama wilayah manual

1. Pilih **Cuaca → Input wilayah manual**, kirim `/cuaca_manual`, atau pilih
   **Input wilayah manual** setelah `/cuaca`.
2. Bot meminta **provinsi → kota/kabupaten → kecamatan → kelurahan/desa** satu per satu.
3. Ketik nama lengkap atau pilih tombol saran. Setiap nama harus cocok secara unik
   dengan daftar Wilayah.id pada induk wilayah yang sudah dipilih.
   Jika nama kota dan kabupaten sama, sertakan `Kota` atau `Kabupaten`.
   Input salah dapat diperbaiki pada tahap yang sama; `/cuaca_manual` memulai ulang.
4. Setelah kelurahan/desa dipilih, bot memvalidasi kode serta nama wilayah pada BMKG
   dan mengirim prakiraan. Alur manual tidak memanggil layanan pemetaan GPS.

Contoh: **Sulawesi Selatan → Kota Makassar → Rappocini → Balla Parang**.
Tombol menampilkan 20 pilihan per halaman dalam dua kolom. Gunakan **Berikutnya / Sebelumnya**
untuk melihat semua wilayah, termasuk Kota Depok di daftar Jawa Barat.
Nama lengkap seperti `Depok` atau `Kota Depok` bisa diketik dari halaman mana saja.
Nama sebagian seperti `Dep` menampilkan hasil pencarian; pilih nama lengkap untuk melanjutkan.
Jika nama ambigu, bot menampilkan kandidat yang perlu dipilih. **Semua wilayah** mengembalikan
daftar lengkap setelah pencarian. Setiap tahap tetap divalidasi terhadap wilayah induknya.
Nama pilihan dan daftar saran hanya ada sementara di memori selama alur input,
lalu dihapus saat selesai, gagal mengambil data, dibatalkan, atau kedaluwarsa terdeteksi.
Setiap permintaan baru harus memilih wilayah lagi, tanpa lokasi default tersimpan.
Permintaan berlaku 5 menit sejak input manual dimulai. `/batal` membatalkan permintaan;
`/menu` juga membatalkan input yang masih berjalan.

### Lokasi GPS

1. Kirim `/cuaca`, atau pilih **Cuaca → Kirim lokasi GPS** dari menu utama.
2. Tekan **Kirim lokasi saya** di Telegram mobile. Alternatif: Lampiran → Lokasi → Kirim lokasi saat ini.
   Titik peta atau tempat bernama (venue) yang dipilih dari menu Lokasi juga didukung;
   prakiraan mengikuti koordinat tempat yang dikirim.
3. Bot mencocokkan kelurahan/desa lalu mengambil prakiraan dari API resmi BMKG.
4. Jawaban berisi wilayah, prakiraan terdekat, suhu, kelembapan, angin, periode berikutnya,
   ringkasan periode tersedia hingga 3 hari, waktu produksi data, dan tautan sumber BMKG.
5. Untuk mengecek lagi, ulangi `/cuaca` dan kirim lokasi baru. `/batal` membatalkan permintaan.

Permintaan lokasi berlaku 5 menit. Bot hanya menerima satu pesan lokasi statis baru setelah
permintaan; live location dan edit lokasi tidak digunakan. Permintaan juga selesai jika
pemetaan/API gagal. Nama kota dalam `/cuaca Jakarta` tidak digunakan sebagai pengganti GPS:
bot tetap menawarkan input manual atau lokasi baru. Akses tetap terbatas pada DM pemilik bot.

### Sumber dan ketepatan wilayah

- **Cuaca:** [API resmi BMKG](https://data.bmkg.go.id/prakiraan-cuaca/),
  `https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=...`.
  BMKG menyediakan prakiraan 3 hari, interval 3 jam, diperbarui 2 kali sehari.
  Bot menampilkan periode mendatang, menggunakan WIB/WITA/WIT sesuai wilayah,
  dan menolak data dengan waktu produksi lebih dari 36 jam. Ringkasan suhu dihitung dari
  periode yang masih tersedia, bukan klaim suhu minimum/maksimum satu hari penuh.
- **Pemetaan GPS:** Nominatim/OpenStreetMap, dengan kode administratif dari
  [Wilayah.id](https://wilayah.id). Ini hanya pemetaan; semua nilai cuaca berasal dari BMKG.
  Nama provinsi, kabupaten/kota, kecamatan, dan kelurahan/desa harus cocok secara unik;
  variasi spasi, tanda hubung, dan awalan administratif dinormalisasi
  (misalnya `Ballaparang` → `Balla Parang`). Pencocokan nama persis diprioritaskan;
  jika normalisasi menghasilkan lebih dari satu kandidat, pemetaan ditolak.
  kode dan nama hasil BMKG diverifikasi lagi. Perbedaan versi kode wilayah antarpenyedia
  dapat menyebabkan pemetaan ditolak. Tidak ada pencocokan nama samar atau fallback cuaca lain.
- Reverse geocoding memakai objek peta terdekat; hasil yang berjarak lebih dari 2 km ditolak.
  Ini **bukan verifikasi batas administratif berbasis poligon**. Periksa nama wilayah pada
  jawaban, terutama di perbatasan. Data peta yang kurang lengkap akan menghasilkan pesan gagal.
- Prakiraan adalah prediksi wilayah, bukan pengamatan real-time di titik GPS, dan tidak
  dijamin 100% sesuai kondisi setempat.

### Lokasi dan layanan pemetaan

Koordinat dikirim ke layanan Nominatim untuk pemetaan saat permintaan diproses. Aplikasi bot
tidak menyimpan koordinat ke database, file, cache, log, atau `user_data`; hanya waktu permintaan
yang ditahan sementara sampai selesai/batal/kedaluwarsa terdeteksi. Riwayat pesan lokasi di
Telegram dan kebijakan data penyedia layanan tetap terpisah dari penyimpanan aplikasi bot.

Endpoint default adalah `https://nominatim.openstreetmap.org`. Penggunaan server publik
mengikuti [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/):
bot pribadi ini hanya melakukan lookup saat diminta, mengantrekan permintaan dengan jarak
minimal 1,1 detik, mengirim User-Agent aplikasi, dan menampilkan atribusi OpenStreetMap.
Tidak ada cron, lookup massal, atau pemantauan lokasi. Jangan jalankan banyak instance yang
mengakibatkan gabungan trafik melebihi 1 permintaan/detik. Endpoint dapat diganti dengan
layanan Nominatim sendiri/kompatibel melalui `.env`, tanpa perubahan kode:

```env
WEATHER_GEOCODER_URL=https://nominatim.openstreetmap.org
```

Tidak diperlukan API key untuk konfigurasi default. Setelah memperbarui project, pasang
dependensi dengan `python -m pip install -r requirements.txt`, lalu restart bot.

## Monitoring Voice Discord

Bot memakai akun Telegram yang sama dengan `ALLOWED_TELEGRAM_USER_ID`; tidak ada bot Telegram kedua. Data disimpan lokal di `data/voice_stats.db` dan semua waktu yang ditampilkan memakai `Asia/Jakarta`.

Untuk menjaga data tetap privat, gunakan bot hanya melalui DM dari akun yang ID-nya ada pada `ALLOWED_TELEGRAM_USER_ID`. Command yang dikirim dari grup atau akun lain akan ditolak; menu command hanya dipasang pada chat owner.

### Persiapan Discord

1. Buat bot pada Discord Developer Portal dan salin tokennya ke `DISCORD_BOT_TOKEN`.
2. Aktifkan **Server Members Intent** di halaman Bot. Bot juga membutuhkan akses melihat channel dan voice state pada server.
3. Undang bot ke server dan isi `DISCORD_GUILD_ID` dengan ID server tersebut.
4. Install ulang dependency Python setelah update project: `python -m pip install -r requirements.txt`.

### Command monitoring

- `/stats` — total seluruh aktivitas dan anggota teraktif.
- `/today` — aktivitas hari ini per member dan channel.
- `/history` atau `/history 7` — ringkasan aktivitas beberapa hari terakhir.
- `/export` atau `/export 2026-09` — membuat dan mengirim Excel. Sheet: Sessions, Daily Summary, Member Summary, dan Channel Summary.
- `/delete 2026-09` — hanya menampilkan peringatan dan jumlah sesi terdampak.
- `/confirm_delete 2026-09` — menghapus setelah periode tersebut pernah berhasil diekspor.
- `/storage` — ukuran database dan rentang data.

Sesi aktif disimpan di SQLite. Saat bot restart dan member masih berada di channel yang sama, sesi dilanjutkan tanpa duplikasi. Jika member keluar ketika bot offline, Discord tidak menyediakan waktu keluar historis; sesi ditutup saat sinkronisasi reconnect mendeteksi member sudah tidak berada di voice channel.

### Backup database

Hentikan bot agar salinan konsisten, lalu jalankan:

```bash
cp data/voice_stats.db data/voice_stats.backup.db
```

Folder `data/`, database, dan Excel export tidak dilacak Git.

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

### Diagnosis dependency dan penyimpanan Termux

Jalankan dari folder project dengan virtual environment yang sama dengan bot:

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
npm install
python check_environment.py
```

Pemeriksa melaporkan import dependency Python, Node.js, FFmpeg, package TikTok,
izin menulis pada folder download/database/export, dan ruang kosong. Exit code 1
menandakan pemeriksaan gagal. Jika Node.js atau FFmpeg belum tersedia:

```bash
pkg install nodejs-lts ffmpeg
```

Path relatif di `.env` sekarang dihitung dari folder project, bukan direktori
terminal saat bot dijalankan. Path absolut dan `~` juga didukung. Simpan project
dan database di direktori home Termux, misalnya `~/tiktok-bot`, agar penyimpanan
database tidak bergantung pada izin shared storage Android.

Jika masih gagal, sertakan traceback dan hasil diagnosis (sensor informasi rahasia).
Error dari perangkat Termux perlu diperiksa langsung; pemeriksaan lokal tidak
menjamin koneksi downloader eksternal tersedia.

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
├── pyproject.toml              # Metadata, dependensi, build package
├── src/
│   └── bmkg_location_resolver/
│       ├── __init__.py         # Public API
│       ├── resolver.py         # GPS, wilayah dan validasi BMKG
│       ├── models.py           # Coordinates dan Forecast
│       ├── exceptions.py       # Error dan pilihan wilayah lanjutan
│       └── telegram.py         # Adapter location/venue tanpa dependency SDK
├── docs/
│   └── resolver.md             # Instalasi dan penggunaan package
├── bot.py                     # Entry point aplikasi Telegram
├── weather.py                 # Compatibility import untuk integrasi lama
├── config.py
├── menus.py
├── discord_voice.py
├── voice_stats.py
├── voice_export.py
├── downloader.py
├── tiktok_api_bridge.js
├── youtube_api_dl.js
├── youtube_api_bridge.js
├── requirements.txt
├── package.json
├── package-lock.json
├── .env.example
├── .gitignore
├── data/                      # Database runtime (bukan isi wheel)
├── downloads/                 # File sementara
├── dist/                      # Wheel/sdist hasil build, diabaikan Git
├── tests/                     # Regresi bot dan package
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
