# Instagram OAuth Setup — Panduan Lengkap

Panduan ini akan membawa Anda step-by-step mendaftar aplikasi di Meta Developer dan menghubungkan Instagram ke bot Anda.

---

## Part 1: Daftar Meta Developer Account

### Langkah 1.1 — Buat Meta Developer Account

1. Buka https://developers.facebook.com
2. Klik **"Get Started"** (pojok kanan atas)
3. Masukkan email dan password Facebook/Meta Anda
4. Jika diminta verifikasi, ikuti instruksi
5. Anda akan redirect ke Meta Developer Dashboard

### Langkah 1.2 — Buat Aplikasi Baru

1. Di Dashboard, klik **"Create App"** (tombol besar di tengah atau menu)
2. Pilih tipe aplikasi: **"Consumer"** (untuk akun personal)
3. Isi informasi:
   - **App Name:** `Honey Instagram Downloader` (atau nama pilihan Anda)
   - **App Contact Email:** Email Anda
   - **App Purpose:** Pilih **"Other"** → Centang "Download Instagram content"
4. Klik **"Create App"**
5. Lengkapi verifikasi keamanan jika diminta

---

## Part 2: Setup Instagram Product

### Langkah 2.1 — Tambah Instagram Product

1. Di halaman App Dashboard, lihat sidebar kiri **"Products"**
2. Cari **"Instagram"** di daftar produk
3. Klik tombol **"Add"** di sebelah Instagram
4. Konfirmasi untuk menambahkan Instagram product
5. Tunggu loading selesai

### Langkah 2.2 — Konfigurasi Instagram Login

1. Di sidebar kiri, buka **Products → Instagram → Instagram Login** (atau Basic Display)
2. Pilih **"Settings"** di submenu
3. Di bagian **"Client OAuth Settings"**, isi:
   - **Valid OAuth Redirect URIs:**
     ```
     https://aldidev.tech/auth/instagram/callback
     https://localhost:8001/auth/instagram/callback
     ```
   - (Tambahkan keduanya — satu untuk production, satu untuk test lokal)
4. Klik **"Save Changes"**

---

## Part 3: Ambil Credentials

### Langkah 3.1 — Dapatkan App ID & App Secret

1. Di sidebar kiri, pilih **Settings → Basic**
2. Copy kedua nilai ini ke notepad sementara:
   - **App ID** (misalnya: `1234567890123456`)
   - **App Secret** (misalnya: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`)
3. **Jangan bagikan App Secret kepada siapa pun**

### Langkah 3.2 — Dapatkan Test User (Instagram Business Account)

Anda perlu Instagram account yang terhubung untuk test.

Opsi A: Gunakan akun Instagram personal Anda sendiri
Opsi B: Buat test user di Instagram untuk development

Untuk simplicity, gunakan **akun Instagram Anda yang sudah ada**. Jangan buat akun baru dulu.

---

## Part 4: Konfigurasi .env di Termux

### Langkah 4.1 — Update .env

1. Di Termux, buka file `.env` di folder bot:
   ```bash
   nano ~/tiktok-bot/.env
   ```

2. Tambahkan baris-baris ini di bagian akhir:
   ```dotenv
   # Instagram OAuth
   INSTAGRAM_APP_ID=YOUR_APP_ID_HERE
   INSTAGRAM_APP_SECRET=YOUR_APP_SECRET_HERE
   INSTAGRAM_REDIRECT_URI=https://aldidev.tech/auth/instagram/callback
   INSTAGRAM_TOKEN_ENCRYPTION_KEY=your-random-32-char-key-here-1234567890ab
   ```

3. Ganti placeholder:
   - `YOUR_APP_ID_HERE` → App ID dari Langkah 3.1
   - `YOUR_APP_SECRET_HERE` → App Secret dari Langkah 3.1
   - `your-random-32-char-key-here-1234567890ab` → Generate key 32 karakter random:
     ```bash
     python3 -c "import secrets; print(secrets.token_hex(16))"
     ```
     Copy output, paste ke `INSTAGRAM_TOKEN_ENCRYPTION_KEY`

4. Simpan: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## Part 5: Tes Credentials

### Langkah 5.1 — Verifikasi Setup

Jalankan di Termux:
```bash
cd ~/tiktok-bot
python3 -c "from config import INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET; print('✓ App ID terdeteksi' if INSTAGRAM_APP_ID else '✗ App ID kosong'); print('✓ App Secret terdeteksi' if INSTAGRAM_APP_SECRET else '✗ App Secret kosong')"
```

Harusnya output:
```
✓ App ID terdeteksi
✓ App Secret terdeteksi
```

Jika ada error, cek lagi `.env` Anda di Langkah 4.1.

---

## Part 6: Cloudflare Tunnel Update

Lihat file **CLOUDFLARE_TUNNEL_UPDATE.md** untuk update konfigurasi Cloudflare Tunnel agar callback service dapat diakses.

---

## Troubleshooting

### "App ID kosong"
- Pastikan file `.env` tersimpan dengan benar
- Restart Termux atau terminal
- Cek ulang copy-paste App ID dari Meta Developer

### "Invalid OAuth Redirect URIs"
- Pastikan URL callback persis: `https://aldidev.tech/auth/instagram/callback`
- Tidak boleh ada slash di akhir atau karakter tambahan

### "App Secret salah format"
- App Secret harus diberikan langsung dari Meta Developer
- Jangan dimodifikasi atau di-decode

---

## Next Steps

1. Setelah setup ini, jalankan callback service: lihat **CALLBACK_SERVICE.md**
2. Test OAuth flow: `/instagram_connect` di bot Telegram
3. Verifikasi token tersimpan di database lokal

---

**Setup ini hanya perlu dilakukan sekali. Setelah itu, token akan dikelola otomatis oleh bot.**
