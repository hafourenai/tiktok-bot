# Telegram Personal AI Auto-Reply

Asisten akun Telegram pribadi berbasis Telethon. Sistem hanya menangani DM teks setelah
pengirim memberi persetujuan eksplisit, menunggu 180 detik, dan membatalkan AI jika pemilik
akun membalas.

## Fitur

- Login akun pribadi MTProto (bukan BotFather) dan session lokal.
- Consent `/aiaktif`, pencabutan `/aimati`, dan handoff `/human`.
- State per chat dan pending job persisten di SQLite.
- Debounce pesan, message versioning, serta validasi ulang sebelum kirim.
- Deteksi balasan manual dari perangkat Telegram mana pun.
- RAG TXT/Markdown menggunakan SQLite FTS5.
- Satu inferensi pada satu waktu dan endpoint OpenAI-compatible.
- CLI owner lokal: `status`, `enable`, `disable`, `set-delay`, `list-chats`,
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

## Alur chat

1. DM pertama tanpa consent tidak disimpan/diproses dan hanya menerima pemberitahuan satu kali.
2. Pengirim mengetik `/aiaktif`.
3. Pesan berikutnya ditampung sementara dan timer diperbarui untuk setiap pesan baru.
4. Balasan manual owner mengubah state menjadi `HUMAN_ACTIVE` dan membatalkan job.
5. Owner mengaktifkan kembali melalui CLI `resume-chat <chat_id>`.
6. `/aimati` menghapus buffer dan menonaktifkan AI untuk chat tersebut.

## Testing

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

Automated test tidak mengakses Telegram nyata. Pengujian dua akun secara manual tetap diperlukan
untuk login/2FA, event dari perangkat lain, FloodWait, jaringan putus, dan perilaku Android.

## Troubleshooting

- **`TG_API_ID ... wajib diisi`**: salin `.env.example` menjadi `.env`, lalu isi kredensial.
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
