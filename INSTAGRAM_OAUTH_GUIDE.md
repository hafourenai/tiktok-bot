# Panduan Instagram OAuth — Satu File

Semua langkah dalam satu tempat, berurutan. Ikuti dari atas ke bawah.

File ini menggantikan 5 dokumen sebelumnya (`INSTAGRAM_SETUP.md`, `CLOUDFLARE_TUNNEL_UPDATE.md`,
`CALLBACK_SERVICE.md`, `BOT_INSTAGRAM_COMMANDS.md`, `INSTAGRAM_OAUTH_SETUP_CHECKLIST.md`).
File lama bisa diabaikan atau dihapus.

---

## Sebelum Mulai: Batasan Penting

Baca ini dulu agar ekspektasi benar.

**Yang bisa dilakukan:**
- Login ke Instagram lewat halaman resmi Instagram/Meta
- Bot menyimpan token secara terenkripsi
- Akses ke media akun Anda sendiri sesuai izin API resmi

**Yang TIDAK bisa dilakukan:**
- Mengunduh Reel/publik milik akun lain lewat OAuth

OAuth tidak memberi izin atas media akun orang lain. Ini batas API resmi Meta, bukan
bug. Kalau target utama Anda downloader Reel publik, panduan ini tidak menyelesaikannya.

**Status kode saat ini:** downloader Instagram masih memakai `instagram-private-api` dengan
username/password, dan **belum** diganti ke OAuth. Lihat Tahap 10.

---

## Tahap 1 — Sync Kode

```sh
cd ~/tiktok-bot
git pull origin main
```

Pastikan file berikut ada:
```sh
ls instagram_oauth.py instagram_db.py callback_service.py
```

Kalau ada yang tidak ada, jangan lanjut. Pull ulang.

---

## Tahap 2 — Install Dependency

```sh
pip install -r requirements-oauth.txt
```

Cek:
```sh
python3 -c "import fastapi, uvicorn, cryptography; print('OK')"
```

---

## Tahap 3 — Verifikasi Konfigurasi Tunnel

Tunnel Anda sudah ada untuk Ollama. Yang perlu diketahui: **tunnel dikelola dari mana?**

### Cara cek

```sh
ps aux | grep cloudflared
```

Lihat di Perintahnya ada `--config` atau tidak.

**Kalau ADA `--config .../config.yml`**
Tunnel dikelola dari file. Lanjut ke Tahap 4A.

**Kalau TIDAK ada `--config`**
Tunnel dikelola dari dashboard Cloudflare. Lanjut ke Tahap 4B.

**Kalau tidak yakin**
Cek juga dashboard Cloudflare dulu — Zero Trust → Networks → Tunnels.
Kalau di sana ada daftar "Public Hostname", itu mode dashboard.

---

## Tahap 4 — Daftarkan Callback di Tunnel

### 4A — Mode File (`config.yml`)

1. Backup dulu:
```sh
cp ~/.cloudflared/config.yml ~/.cloudflared/config.yml.backup
```

2. Lihat isi sekarang:
```sh
cat ~/.cloudflared/config.yml
```

3. **Penting:** Ollama Anda kemungkinan memakai domain root. Kalau begitu, memakai path
   `/ollama/*` akan **memutus** Ollama yang sudah jalan.

**Pilihan A — Subdomain terpisah (paling aman, Ollama tidak tersentuh):**
```yaml
ingress:
  - hostname: aldidev.tech
    service: http://localhost:8000

  - hostname: auth.aldidev.tech
    service: http://localhost:8001

  - service: http_status:404
```

**Pilihan B — Path di domain yang sama (hanya jika Ollama memang ada di `/ollama/*`):**
```yaml
ingress:
  - hostname: aldidev.tech
    path: /ollama/*
    service: http://localhost:8000

  - hostname: aldidev.tech
    path: /auth/instagram/*
    service: http://localhost:8001

  - service: http_status:404
```

Rule `/auth/instagram/*` wajib **di atas** `http_status:404`.

4. Restart tunnel:
```sh
pkill cloudflared
cloudflared tunnel run
```

5. **Cek subdomain sudah ada di DNS.** Untuk Pilihan A, buka dashboard Cloudflare →
   DNS Records. Harus ada CNAME `auth` → `<tunnel-id>`. Kalau belum ada, buat.
   Tunnel yang disebut "public hostname" di dashboard otomatisnya sudah di-DNS-kan;
   kalau Anda hanya edit file config lokal, Anda **harus** buat record-nya manual.

### 4B — Mode Dashboard

1. Dashboard Cloudflare → Zero Trust → Networks → Tunnels
2. Klik tunnel yang dipakai Ollama
3. **Public Hostname** → **Add a public hostname**
4. Isi:
   - Subdomain: `auth`
   - Domain: `aldidev.tech`
   - Path: kosongkan
   - Service: `http://localhost:8001`
5. Save

Tidak perlu buat DNS record manual — dashboard mengurusnya.

---

## Tahap 5 — Daftar di Meta Developer

1. Buka https://developers.facebook.com
2. **Create App** → tipe **Consumer**
3. Nama app, isi kontak, submit
4. Dari sidebar **Products**, tambahkan produk Instagram
5. Konfigurasi **Client OAuth Settings**
6. Masukkan **Valid OAuth Redirect URIs:**
   ```
   https://aldidev.tech/auth/instagram/callback
   ```
   (atau `https://auth.aldidev.tech/auth/instagram/callback` — harus **persis sama**
   dengan yang Anda pakai di Tahap 4 dan Tahap 7)

   > Penting: tanpa `https://`, tanpa slash di akhir, tanpa port.

7. Simpan. Buka **Settings → Basic**, catat **App ID** dan **App Secret**

---

## Tahap 6 — Isi `.env`

```sh
nano ~/tiktok-bot/.env
```

Tambahkan:

```dotenv
INSTAGRAM_APP_ID=<App ID dari Meta>
INSTAGRAM_APP_SECRET=<App Secret dari Meta>
INSTAGRAM_REDIRECT_URI=https://aldidev.tech/auth/instagram/callback
INSTAGRAM_TOKEN_ENCRYPTION_KEY=<hasil perintah di bawah>
```

Generate encryption key:
```sh
python3 -c "import secrets; print(secrets.token_hex(16))"
```

Simpan: `Ctrl+O` → `Enter` → `Ctrl+X`

### Verifikasi (tidak menampilkan nilai rahasia)

```sh
python3 -c "
from config import INSTAGRAM_APP_ID as A, INSTAGRAM_APP_SECRET as S, INSTAGRAM_REDIRECT_URI as R, INSTAGRAM_TOKEN_ENCRYPTION_KEY as K
print('app_id     :', bool(A))
print('app_secret :', bool(S))
print('redirect   :', R or 'KOSONG')
print('key length :', len(K))
"
```

Harus: `True`, `True`, URL terisi, `32`.

---

## Tahap 7 — Jalankan Callback Service

Terminal terpisah:

```sh
cd ~/tiktok-bot
python3 callback_service.py
```

Output yang diharapkan:
```
Uvicorn running on http://127.0.0.1:8001
```

Test lokal di terminal lain:
```sh
curl http://localhost:8001/health
```
Harus: `{"status":"ok"}`

---

## Tahap 8 — Verifikasi dari Luar

Tunnel harus aktif. Dari perangkat mana pun (HP/laptop):

```sh
curl https://aldidev.tech/auth/instagram/health
```

Kalau hasilnya `{"status":"ok"}` → tunnel dan DNS sudah benar.

Kalau gagal:
- `502`/`503` → tunnel belum jalan, atau service tidak jalan
- `404` → hostname atau path tidak terdaftar di tunnel
- timeout → DNS belum propagasi (tunggu 1-2 menit)

---

## Tahap 9 — Verifikasi Token Flow

Belum ada command bot, tapi bisa tes langsung:

```sh
python3 -c "
from instagram_db import init_db
init_db()
print('database OK')
"
```

Lalu cek endpoint callback menerima parameter (tanpa code asli):
```sh
curl -i "https://aldidev.tech/auth/instagram/callback?code=test&state=test"
```

Harus mengembalikan HTML "Session Expired". Ini **membuktikan route berjalan** end-to-end.

---

## Tahap 10 — Yang Belum Selesai

Semua langkah di atas menyiapkan infrastruktur OAuth. **Belum ada tombol bot untuk login**,
dan downloader masih memakai password.

### 10.1 Downloader publik masih pakai password

`downloader.py` masih membaca `INSTAGRAM_USERNAME` / `INSTAGRAM_PASSWORD`, sementara
`config.py` sudah tidak menyediakannya lagi. Jadi jalur unduh Reel publik **akan gagal**.

Pilih salah satu:
- **(a)** Kembalikan `INSTAGRAM_USERNAME`/`INSTAGRAM_PASSWORD` ke `.env` supaya jalur lama jalan lagi
- **(b)** Hapus fitur download Instagram publik sepenuhnya
- **(c)** Ganti ke `yt-dlp`, yang sudah mendukung Instagram tanpa login untuk konten publik

### 10.2 Belum ada command bot

`/instagram_connect`, `/instagram_status`, `/instagram_disconnect` belum ada di `bot.py`.
Contoh handlers ada di `BOT_INSTAGRAM_COMMANDS.md` tapi belum diimplementasikan.

---

## Ringkasan Urutan

| # | Tahap | Perintah utama |
|---|-------|----------------|
| 1 | Sync kode | `git pull origin main` |
| 2 | Install dependency | `pip install -r requirements-oauth.txt` |
| 3 | Cek mode tunnel | `ps aux \| grep cloudflared` |
| 4 | Daftarkan callback | edit `config.yml` atau dashboard |
| 5 | Daftar Meta Developer | catat App ID + Secret |
| 6 | Isi `.env` | 4 variabel |
| 7 | Jalankan callback | `python3 callback_service.py` |
| 8 | Test dari luar | `curl https://.../health` |
| 9 | Test token flow | `curl .../callback?code=test&state=test` |
| 10 | Selesaikan sisa | lihat 10.1 dan 10.2 |

---

## Troubleshooting

| Gejala | Penyebab | Solusi |
|--------|----------|--------|
| `App ID kosong` | `.env` salah edit | Cek ulang, pastikan tidak ada spasi |
| `502` dari domain | Tunnel/service mati | Jalankan ulang `cloudflared` dan `callback_service.py` |
| `404` dari domain | Hostname/path tidak terdaftar | Ulangi Tahap 4 |
| Callback ditolak Meta | Redirect URI tidak persis sama | Bandingkan karakter per karakter |
| `Session Expired` | State sudah dipakai/expired | Normal — restart flow dari awal |
| Downloader gagal | Lihat 10.1 | Jalankan yt-dlp atau kembalikan password |

---

## Catatan Keamanan

- Password Instagram **tidak pernah** masuk ke bot (kalau OAuth dipakai)
- Token disimpan terenkripsi di `data/instagram.db`
- `App Secret` hanya di `.env`, jangan di-commit
- `.env` sudah di-`.gitignore` — pastikan begitu