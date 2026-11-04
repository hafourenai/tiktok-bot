# Telegram Personal AI Auto-Reply

Asisten akun Telegram pribadi berbasis Telethon. Semua DM teks dari manusia otomatis
aktif secara default, menunggu 180 detik, dan membatalkan AI jika pemilik akun membalas.
Grup, channel, dan pengirim bot tidak diproses. Uji dengan akun kedua sebelum dipakai.

## Fitur

- Login akun pribadi MTProto (bukan BotFather) dan session lokal.
- Kontrol global `chat-enable` / `chat-disable` dari CLI Termux tanpa ID chat.
- Pengecualian per chat tetap didukung; pengguna tidak bisa mengubah kontrol admin.
- Katalog harga/stok dari CSV publik atau Google Sheets privat, tanpa inferensi LLM untuk jawaban katalog.
- Setiap balasan ditutup dengan penanda `---\nBalasan Otomatis`, tanpa label sumber/nama file knowledge. Emoji diperbolehkan seperlunya.
- **Rate limit spam**: jika pelanggan mengirim ≥5 pesan dalam 60 detik, bot kirim acknowledgment sekali lalu abaikan pesan berikutnya hingga window habis.
- State per chat dan pending job persisten di SQLite.
- Debounce pesan, message versioning, serta validasi ulang sebelum kirim.
- Deteksi balasan manual dari perangkat Telegram mana pun.
- RAG TXT/Markdown menggunakan SQLite FTS5.
- Satu inferensi pada satu waktu dan endpoint OpenAI-compatible.
- Reconnect otomatis saat jaringan terputus (Network is Unreachable).
- CLI owner lokal: `chat-enable`, `chat-disable`, `list-chats`, `enable-chat`, `disable-chat`, `set-delay`,
  `pause-chat`, `resume-chat`, `reindex`, dan `exit`.
- Isi pesan tidak masuk log; buffer pesan dihapus setelah selesai, revoke, handoff, atau restart.

## Peringatan privasi

Konfigurasi contoh menggunakan `llama-server` lokal di `127.0.0.1:8080`, sehingga pesan
tidak dikirim ke layanan LLM eksternal. Aplikasi menolak endpoint non-localhost kecuali
`LLM_ALLOW_REMOTE=true`; jangan mengaktifkannya untuk deployment lokal.

Gunakan sesuai [Telegram API Terms](https://core.telegram.org/api/terms) dan
[Content Licensing](https://telegram.org/tos/content-licensing). Uji dengan akun kedua dahulu.

## Setup Termux

1. Pasang Termux dari F-Droid, lalu dari direktori proyek:

   ```bash
   chmod +x scripts/setup_termux.sh
   ./scripts/setup_termux.sh
   ```

2. Buat API ID/hash di <https://my.telegram.org> → **API development tools**.
3. Salin `.env.example` ke `.env` jika belum dibuat oleh script, lalu isi `TG_API_ID` dan
   `TG_API_HASH`. Jangan membagikan file ini. Ini `.env` milik `telegram_personal_ai/`,
   bukan `.env` bot utama di root repo.
4. Isi file `.txt` atau `.md` di `knowledge/`, lalu uji indeks:

   ```bash
   python -m scripts.build_index
   ```

5. Jalankan `llama-server` terlebih dahulu di sesi Termux lain (lihat di bawah), lalu
   uji endpoint model dan jalankan aplikasi:

   ```bash
   python -m scripts.test_model
   python main.py
   ```

Login pertama meminta nomor, kode Telegram, dan password 2FA bila aktif. File session memberi
akses ke akun; jangan disalin atau di-commit.

### Menjaga proses di Android

```bash
termux-wake-lock
python main.py
```

Nonaktifkan optimasi baterai untuk Termux bila perlu. Android tetap dapat menghentikan proses;
aplikasi tidak menjanjikan uptime 24/7. Setelah restart, job lama dibatalkan agar tidak mengirim
balasan basi.

## Model lokal (deployment akhir)

Gunakan build `llama.cpp` ARM64 yang sudah Anda siapkan. Dari direktori build `llama.cpp`,
jalankan pada sesi Termux terpisah (sesuaikan path model dengan lokasi file GGUF Anda):

```bash
./build/bin/llama-server \
  --model ~/models/qwen3-0.6b-q4.gguf \
  --alias qwen3-0.6b \
  --host 127.0.0.1 \
  --port 8080 \
  --ctx-size 1024 \
  --parallel 1 \
  --threads 4 \
  --n-predict 160 \
  --no-ui
```

Isi LLM di `telegram_personal_ai/.env` (nilai default di `.env.example` sudah sama):

```env
LLM_BASE_URL=http://127.0.0.1:8080
LLM_MODEL=qwen3-0.6b
LLM_ALLOW_REMOTE=false
LLM_TIMEOUT_SECONDS=120
LLM_MAX_TOKENS=160
LLM_TEMPERATURE=0.2
```

`LLM_MODEL` harus cocok dengan `--alias`. URL root di atas otomatis diubah aplikasi menjadi
`http://127.0.0.1:8080/v1/chat/completions`. Context dan paralelisme diatur lewat flag
`llama-server`, bukan variabel `.env`; aplikasi juga membatasi satu permintaan LLM sekaligus.
`--threads 4` dapat disesuaikan dengan perangkat. Model dan performa tetap perlu diuji langsung
di Termux; proyek tidak mengklaim sudah diuji pada semua Android.

## CLI Termux

Setelah `python main.py` berjalan, ketik di prompt `ai-admin>`:

```text
list-chats                    — lihat semua chat dan statusnya
chat-enable                   — aktifkan AI global (default aktif)
chat-disable                  — hentikan seluruh balasan otomatis
enable-chat <CHAT_ID>         — aktifkan AI untuk chat tersebut
disable-chat <CHAT_ID>        — nonaktifkan AI untuk chat tersebut
pause-chat <CHAT_ID>          — jeda sementara (gunakan resume-chat untuk lanjut)
resume-chat <CHAT_ID>         — lanjutkan setelah pause-chat
set-delay <DETIK>             — ubah delay balasan (default 180 s)
reindex                       — indeks ulang knowledge
exit                          — matikan aplikasi
```

Chat baru tidak memerlukan aktivasi. `chat-enable` tidak membatalkan pengecualian
`disable-chat <CHAT_ID>`; gunakan `enable-chat <CHAT_ID>` untuk menghapus pengecualian itu.
Sakelar global tersimpan di SQLite dan tetap berlaku setelah restart. `chat-disable`
membatalkan job lama; mengaktifkannya kembali tidak memutar ulang pesan saat AI mati.
Migrasi mengaktifkan chat lama yang belum pernah dikonfigurasi, tetapi mempertahankan
chat yang secara eksplisit dinonaktifkan pemilik. Tidak ada pesan historis yang dikirim ulang.

### Flow: Auto-Resume setelah Manual Reply

1. **AI global aktif secara default (atau aktifkan lagi dari CLI):**
   ```
    ai-admin> chat-enable
   ```
    → DM baru otomatis aktif, tanpa ID chat

2. **User kirim pesan:**
   ```
   User: "Halo, kapan buka?"
   ```
   → AI delay 180s lalu jawab otomatis

3. **Pemilik balas manual dari Telegram (HP/device apapun):**
   ```
   Pemilik: "Halo, buka jam 9"
   ```
   → Sistem **otomatis** detect → state=`HUMAN_ACTIVE` (pause), `ai_enabled` tetap `1`

4. **User kirim pesan lagi:**
   ```
   User: "Terimakasih!"
   ```
   → AI **otomatis resume** (state `HUMAN_ACTIVE` → `IDLE`) → delay → jawab

5. **Cycle repeat:** Manual reply → Auto-resume → Jawab → Manual reply → ...

**Tidak perlu perintah CLI tambahan.** Pemilik hanya perlu:
- `chat-enable` untuk mengaktifkan AI global setelah dimatikan
- `disable-chat` jika ingin menonaktifkan selamanya
- `pause-chat` / `resume-chat` untuk jeda manual yang eksplisit

### Perbedaan `pause-chat` vs Manual Reply

- **`pause-chat <CHAT_ID>`** dari CLI: Jeda manual yang eksplisit. Gunakan `resume-chat` untuk lanjut.
- **Manual reply** dari Telegram: Jeda otomatis sementara. AI **otomatis resume** pada pesan berikutnya.

## Best practice jaringan di Termux (Network is Unreachable)

Android dapat memutus koneksi saat layar mati atau memindahkan jaringan (WiFi ↔ data).
Langkah untuk meminimalkan putus koneksi:

- Jalankan `termux-wake-lock` sebelum `python main.py`.
- Nonaktifkan optimasi baterai untuk Termux di **Pengaturan → Baterai**.
- Jalankan di dalam `tmux` agar sesi tidak hilang jika Termux pindah ke background.
- Aplikasi sudah dilengkapi reconnect otomatis dengan backoff 10 → 30 → 60 → 120 detik.
  Job yang tertunda dibatalkan saat reconnect agar tidak mengirim balasan basi.
- Jika sering putus, set `TG_TIMEOUT_SECONDS=60` di `.env` untuk timeout yang lebih toleran.

## Katalog menu, harga, dan stok Google Sheets

Harga/stok dijawab langsung dari data terstruktur, bukan disimpulkan oleh LLM.
FAQ, layanan, dan keluhan tetap memakai knowledge TXT/Markdown + LLM lokal.
Delay balasan yang sudah ada tetap berlaku untuk keduanya.

### CSV publik tanpa API key (paling sederhana)

Gunakan tautan Google Sheets **Publish to web → CSV**, seperti URL `/pub?output=csv`.
Tidak perlu mengaktifkan Google Sheets API, membuat service account, memasang google-auth,
atau menyimpan key JSON. **Data yang dipublikasikan dapat dibaca publik**; jangan sertakan
informasi pelanggan, kredensial, atau data pribadi di tab yang dipublikasikan.

Di `telegram_personal_ai/.env`, isi:

```env
CATALOG_CSV_URL=https://docs.google.com/spreadsheets/d/e/ID_PUBLIKASI/pub?output=csv
CATALOG_CACHE_SECONDS=30
CATALOG_TIMEOUT_SECONDS=15
```

`CATALOG_CSV_URL` diprioritaskan atas `CATALOG_SHEET_ID`; kredensial API diabaikan
dalam mode ini. Header baris pertama harus:

```csv
kode,nama,harga,stok,aktif,deskripsi,alias
LELE,Paket Lele,17300,12,TRUE,"Nasi, lele, sambal",lele goreng
AYAM,Paket Ayam,18000,0,TRUE,"Nasi, ayam, sambal",ayam goreng
```

Isi ini di sel spreadsheet, bukan satu sel berisi seluruh CSV. Harga/stok harus
angka bulat tanpa format mata uang/pemisah ribuan (gunakan format Plain text atau angka
tanpa pemisah ribuan); CSV Google mengekspor format tampilan, bukan nilai mentah API.
Pilih tab menu yang benar ketika memublikasikan. Respons CSV kosong/HTML/header salah
tidak dianggap sebagai stok kosong: bot menyatakan data belum dapat diperiksa.

Instal `requirements.txt` seperti biasa lalu restart bot. Selain cache bot,
Google dapat menunda pembaruan hasil publikasi; ini bukan stok real-time yang dijamin.
`CATALOG_CACHE_SECONDS=0` hanya mematikan cache bot, bukan cache publikasi Google.

Jika bot menampilkan `Katalog tidak tersedia`, uji langsung dari direktori
`telegram_personal_ai` dengan `python -m scripts.test_catalog`. Tes ini memakai `.env`
yang sama tanpa menghubungi Telegram atau LLM. Error validasi menyebut nomor baris
bermasalah pada CSV; setelah memperbaiki sheet, tunggu publikasi Google diperbarui.

### Alternatif: persiapan sheet privat melalui API

1. Aktifkan **Google Sheets API** di project Google Cloud Anda.
2. Buat service account, unduh key JSON, simpan sebagai
   `telegram_personal_ai/data/google-service-account.json`. Folder `data/` diabaikan Git.
   Jangan taruh key dalam knowledge atau membagikannya; pada Termux gunakan `chmod 600`.
3. Share spreadsheet **hanya sebagai Viewer** ke `client_email` service account.
   Tidak perlu opsi "Publish to web" atau akses publik, maupun role Editor.
4. Buat tab **Menu**, dengan header baris pertama berikut (kolom `alias` opsional):

   | kode | nama | harga | stok | aktif | deskripsi | alias |
   |---|---|---:|---:|---|---|---|
   | LELE | Paket Lele | 17300 | 12 | TRUE | Nasi, lele, sambal | lele goreng\|paket lele goreng |
   | AYAM | Paket Ayam | 18000 | 0 | TRUE | Nasi, ayam, sambal | ayam goreng |

   Ini hanya contoh; isi harga/stok asli milik Anda. Harga dalam rupiah bulat,
   stok bilangan bulat nonnegatif, **bukan teks** `Rp17.300`. `aktif` harus TRUE/FALSE
   (checkbox boleh). Gunakan kode unik dan alias yang tidak ambigu, dipisahkan `|`.
   `stok=0` berarti habis; `aktif=FALSE` tidak ditampilkan pada katalog umum,
   tetapi pertanyaan spesifik tetap dijawab "Tidak tersedia".

5. Di `telegram_personal_ai/.env`, tambahkan:

   ```env
   CATALOG_SHEET_ID=ID_DARI_URL_SPREADSHEET
   CATALOG_SHEET_RANGE=Menu!A1:G1000
   GOOGLE_APPLICATION_CREDENTIALS=data/google-service-account.json
   CATALOG_CACHE_SECONDS=30
   CATALOG_TIMEOUT_SECONDS=15
   ```

   ID adalah bagian antara `/d/` dan `/edit` pada URL Google Sheets, bukan `gid`.
   Range harus mencakup header dan semua baris menu. Perbesar jika lebih dari 999 menu.
   Kosongkan `CATALOG_CSV_URL` untuk memakai API privat. Kosongkan kedua sumber untuk
   menonaktifkan integrasi dan memakai RAG seperti semula.

6. Instal dependensi dari direktori `telegram_personal_ai`, lalu restart:

   ```bash
   # Termux: gunakan paket prebuilt agar tidak perlu build cryptography/Rust di HP
   pkg install python-cryptography
   python -m pip install -r requirements-sheets-api.txt
   python main.py
   ```

### Perilaku jawaban

- "Daftar menu" / "Harga menu berapa?" → semua menu aktif, harga, deskripsi, dan stok.
- "Harga lele?" → hanya menu yang cocok dengan kode/nama/alias.
- "Ada lele dan ayam?" → kedua menu, termasuk status habis.
- Nama yang tidak cocok → minta klarifikasi, bukan mengarang harga.
- Keluhan dan FAQ → tetap RAG/LLM; tambahkan sinonim menu pada kolom `alias` untuk pencarian.
- Data kosong/salah, timeout, atau izin Google bermasalah → informasikan data belum
  dapat diperiksa. Jangan memakai cache kedaluwarsa untuk menyatakan stok tersedia.

Cache adalah snapshot maksimal 30 detik, **bukan sinkronisasi instan/push**.
Gunakan `CATALOG_CACHE_SECONDS=0` untuk membaca sheet setiap pertanyaan.
Bot hanya membaca: tidak mengurangi stok, menyimpan pesanan, atau menjamin reservasi.
Stok akurat hanya jika Anda/sistem kasir memperbarui sheet. Setiap jawaban menampilkan
waktu pemeriksaan. Katalog panjang dikirim dalam beberapa pesan teks.

Saat integrasi aktif, hapus harga/stok lama dari knowledge dan sisakan kebijakan/FAQ
agar pertanyaan non-katalog tidak mengambil angka usang. Google hanya menerima permintaan
CSV atau ID/range dan kredensial API (mode privat), bukan isi pesan pelanggan. Pengujian otomatis menggunakan
mock API; uji izin service account dan perubahan stok asli sebelum produksi.

## Testing

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

Automated test tidak mengakses Telegram nyata. Pengujian dua akun secara manual tetap diperlukan
untuk login/2FA, event dari perangkat lain, FloodWait, jaringan putus, dan perilaku Android.

## Troubleshooting

- **`TG_API_ID ... wajib diisi`**: salin `.env.example` menjadi `.env`, lalu isi kredensial.
- **Network is Unreachable**: jalankan `termux-wake-lock`, nonaktifkan optimasi baterai
  untuk Termux, dan gunakan `tmux`. Aplikasi akan reconnect otomatis.
- **Remote endpoint ditolak**: set `LLM_ALLOW_REMOTE=true` hanya setelah memahami implikasi privasi.
- **LLM timeout/offline**: pengguna menerima fallback dan chat masuk human handoff.
- **Session revoked**: hentikan aplikasi, pindahkan session lama ke tempat aman, lalu login ulang.
- **FTS5 unavailable**: gunakan build Python Termux resmi yang menyertakan SQLite FTS5.
- **RAM habis**: kecilkan model quantization/context/output; jangan menambah worker inferensi.

## Keterbatasan

- Event balasan manual perangkat lain dapat tiba terlambat. Pemeriksaan versi meminimalkan tetapi
  tidak dapat menghilangkan race setelah request kirim sudah diterima Telegram.
- FTS keyword/BM25 tidak memahami sinonim sebaik embedding; hasil kosong selalu dialihkan ke manusia.
- Media, voice note, grup, channel, bot, broadcast, downloader, dan transaksi tidak didukung.
