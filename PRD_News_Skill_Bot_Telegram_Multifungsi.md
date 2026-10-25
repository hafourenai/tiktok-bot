# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## News Scraper & AI Summarization Skill — Bot Telegram Multifungsi

**Versi:** 1.0  
**Tanggal:** 25 Oktober 2026  
**Status:** Siap menjadi acuan implementasi; belum diimplementasikan  
**Pemilik produk:** Pengelola bot Telegram pribadi  
**Platform:** Python, `python-telegram-bot`, satu host lokal  
**Prioritas:** MVP / fitur tambahan tanpa regresi

---

## 1. Ringkasan Produk

Menambahkan **News Skill** pada **bot Telegram multifungsi yang sudah berjalan** (converter file, downloader, prakiraan cuaca BMKG, dan Discord Voice Monitor). Saat pemilik menjalankan `/berita` atau `/berita <kategori>`, bot mengambil berita terbaru dari feed resmi media nasional dan internasional, memvalidasi serta menyaring artikel, kemudian meminta **LLM lokal Qwen3 0.6B** membuat **ringkasan terpisah untuk setiap artikel**. Balasan memuat judul, penerbit, waktu terbit, ringkasan AI, dan tautan sumber asli.

News Skill **bukan** bagian dari proyek `telegram_personal_ai` / Personal AI Assistant. Kedua aplikasi memiliki direktori proyek, Python virtual environment, `.env`, token/sesi Telegram, dan database yang **berbeda**; keduanya hanya menjadi klien dari **satu proses `llama-server` yang sama** pada `http://127.0.0.1:8080` karena berjalan pada host yang sama. Tidak ada proses pengambilan berita otomatis atau push notification terjadwal.

**Keputusan produk terkunci:** (1) kedua bot dan LLM pada satu host; (2) sumber nasional dan internasional; (3) LLM merangkum setiap artikel secara individual; (4) hanya dijalankan lewat command; (5) apabila LLM gagal, tampilkan cuplikan asli tanpa menyatakan bahwa itu ringkasan AI.

## 2. Konteks Sistem Eksisting

Analisis kode yang diberikan menunjukkan:

- Bot multifungsi menggunakan `Application.builder()`, `CommandHandler`, `CallbackQueryHandler`, `MessageHandler`, dan `application.run_polling()` dari `python-telegram-bot`, **bukan Telethon**.
- Pemeriksaan `is_allowed(update)` membatasi pemakaian ke `ALLOWED_USER_ID` di chat pribadi; handler sensitif harus menggunakannya. `deny()` tersedia untuk akses ditolak.
- Menu dibangun melalui `menu_content()` / `menu_commands()` dari `menus.py`, diregistrasikan kembali oleh `show_menu()` dan `post_init()`.
- Bot menggunakan `application.bot_data` untuk service bersama, serta `post_shutdown()` untuk pembersihan service.
- Fitur downloader memiliki `DOWNLOAD_LIMIT = asyncio.Semaphore(2)`; News Skill harus memiliki limit tersendiri dan tidak menahan event loop selama fetching, parsing, atau inference. Pada PTB, handler News juga harus **non-blocking pada dispatcher** (mis. `block=False` dengan pembatasan task aktif), karena sekadar memakai fungsi `async` tidak menjamin update Telegram berikutnya diproses secara paralel.
- Fitur existing yang tidak boleh berubah perilakunya: converter PDF/Office/gambar, kompres PDF, TikTok/YouTube/Instagram downloader, TikTok profile stalk, cuaca BMKG, Discord Voice Monitor, statistik dan ekspor.

**Batas informasi:** File yang diterima memuat modul utama, tetapi tidak memuat seluruh implementasi `menus.py`, `config.py`, versi dependensi, dan file deployment. Perubahan pada file tersebut harus diverifikasi terhadap repositori asli sebelum coding; PRD tidak mengasumsikan skema internal yang belum terlihat.

## 3. Masalah, Tujuan, dan Metrik

### 3.1 Masalah

Pemilik bot perlu membaca informasi terkini tanpa berpindah ke banyak portal berita. Model AI lokal tidak memiliki akses real-time secara bawaan; ia memerlukan konten faktual dari penerbit sebelum melakukan peringkasan.

### 3.2 Tujuan (Goals)

1. Menyediakan daftar **berita aktual nasional dan internasional** atas permintaan pemilik bot.
2. Menghasilkan **ringkasan faktual bahasa Indonesia untuk masing-masing artikel** menggunakan Qwen3 0.6B lokal.
3. Menampilkan atribusi penerbit, tanggal terbit, dan tautan asli pada setiap entri.
4. Tetap berguna saat satu feed, ekstraksi artikel, atau LLM bermasalah.
5. Menambah fitur tanpa mengganti arsitektur bot dan tanpa menggabungkan environment proyek lain.

### 3.3 Ukuran keberhasilan awal (target internal, dievaluasi di perangkat nyata)

- 100% command News Skill tunduk pada pemeriksaan akses pemilik.
- 100% entri yang dikirim memiliki judul, penerbit, dan URL asli yang valid.
- Pada pengujian manual 20 artikel beragam, minimal 18 ringkasan tidak menambahkan fakta substantif yang tidak didukung masukan; hasil gagal harus diperbaiki sebelum rilis.
- Feed rusak, HTTP error, dan LLM offline tidak menyebabkan crash bot atau menghilangkan command lain.
- Maksimum lima artikel per request secara default; proses dibatasi agar tetap responsif. Waktu respons akhir diukur di host asli, bukan dijanjikan sebelum benchmarking.

## 4. Ruang Lingkup

### 4.1 Termasuk pada MVP (P0)

- `/berita` dan `/berita <kategori>` untuk berita terbaru; kategori: `nasional`, `internasional`, `teknologi`, `ekonomi`, `politik`, `olahraga`.
- Feed resmi ANTARA (Indonesia) dan The Guardian (internasional) sebagai baseline dua penerbit; pengelompokan bahasa/kategori melalui konfigurasi, bukan asumsi semua kategori tersedia pada semua sumber.
- Ambil metadata RSS; ekstraksi isi artikel hanya jika diperbolehkan dan tersedia. Prioritaskan feed resmi, bukan crawling tanpa batas.
- Dedup URL dan judul serupa; sortir berdasarkan waktu terbit; konversi waktu tampilan ke `Asia/Jakarta`.
- Ringkasan AI **per artikel**, maksimal 2–3 kalimat atau sekitar 50–90 kata bahasa Indonesia, berbasis teks yang benar-benar diambil.
- Saat teks hanya berupa excerpt, ringkasan dibuat dengan keterbatasan eksplisit atau excerpt langsung ditampilkan; jangan mengklaim telah membaca isi penuh.
- Fallback berupa judul + cuplikan asli + waktu + sumber + URL ketika LLM gagal.
- Status proses ke Telegram, cache dan SQLite terpisah, log sanitasi, timeout, retry terbatas, serta error handling.
- Integrasi command/menu menggunakan pola `python-telegram-bot` dan `ALLOWED_USER_ID` yang sudah dipakai.

### 4.2 Peningkatan berikutnya (P1, tidak wajib pada MVP)

- `/berita cari <kata-kunci>` untuk pencarian pada feed/artikel **yang sudah berhasil diambil**; pencarian web bebas memerlukan sumber/API serta kebijakan tersendiri.
- Tombol inline 'Perbarui', 'Berikutnya', dan pemilihan kategori, dengan callback token pendek dan masa berlaku.
- Penambahan penerbit lain setelah validasi feed resmi, izin, dan pengujian stabilitas.
- Indikator kualitas dan umpan balik ringkasan.

### 4.3 Di luar ruang lingkup

Penjadwalan berita, push otomatis, chatbot berita bebas, forecasting, scraping akun login/paywall, penyalinan isi artikel lengkap ke Telegram, penggantian framework bot, penggabungan database Personal AI, serta perubahan pada `/aiaktif`, RAG, atau auto-reply Personal AI Assistant.

## 5. Pengguna, Command, dan Alur

**Pengguna utama:** Pemilik bot yang cocok dengan `ALLOWED_USER_ID` dalam chat pribadi. Pengguna lain menerima respons akses ditolak mengikuti mekanisme bot saat ini.

| ID | Input | Perilaku yang diharapkan |
|---|---|---|
| UC-01 | `/berita` | Memilih hingga 5 berita terbaru lintas sumber nasional/internasional, lalu merangkum setiap artikel. |
| UC-02 | `/berita nasional` | Hanya sumber/konten kategori nasional yang dipetakan secara eksplisit. |
| UC-03 | `/berita internasional` | Berita internasional dari feed yang dikonfigurasi; tidak otomatis berarti semua artikel berbahasa Inggris. |
| UC-04 | `/berita teknologi` | Filter kanal teknologi yang tersedia, lalu peringkas per artikel. |
| UC-05 | `/berita ekonomi`, `/berita politik`, `/berita olahraga` | Filter kanal sesuai kategori, dengan pemberitahuan jika suatu sumber tidak memiliki feed kategori terkait. |
| UC-06 | Kategori tidak dikenal | Tampilkan bantuan singkat berisi kategori yang valid; jangan melakukan fetch. |
| UC-07 | LLM mati / timeout | Tampilkan artikel yang tersedia dengan label 'Cuplikan sumber (tanpa ringkasan AI)'. |
| UC-08 | Semua feed gagal | Tampilkan pesan 'Belum berhasil mengambil berita terbaru' dan sarankan coba lagi; jangan menyajikan cache lama sebagai berita baru tanpa label. |

**Alur inti:** validasi user dan input → kirim status 'Mengambil berita...' → baca cache segar atau fetch RSS terpilih → validasi domain/metadata/tanggal → dedup dan urutkan → ekstrak isi yang diizinkan → ringkas artikel satu per satu menggunakan LLM lokal → bangun pesan HTML aman → kirim hasil, atau fallback per artikel → catat metrik non-sensitif.

**Aturan tanggal:** Utamakan artikel yang diterbitkan dalam 48 jam terakhir. Jika tidak cukup, boleh tampilkan artikel yang lebih lama dengan label 'Artikel lebih lama'; jangan salah mengartikan waktu scraping sebagai waktu publikasi. Tanggal yang hilang diberi label 'Waktu terbit tidak tersedia' dan prioritas paling akhir; timestamp masa depan yang tidak masuk akal harus ditandai/ditolak.

**Respons minimum setiap artikel:** nomor, judul, penerbit, waktu terbit atau label ketidaktersediaan, ringkasan AI **atau** cuplikan sumber yang diberi label jelas, dan URL HTTPS artikel asli. Hindari melebihi batas pesan Telegram: pecah pesan menjadi beberapa balasan jika diperlukan, dengan `html.escape` untuk teks sumber dan model.

## 6. Sumber Berita dan Kebijakan Akses

| Sumber | Wilayah | Kanal awal | Status dan batas |
|---|---|---|---|
| ANTARA News | Nasional | terkini, politik, ekonomi, teknologi, olahraga; juga dunia | Halaman RSS resmi mencantumkan URL feed. Pemakaian konten harus mengikuti syarat penerbit. |
| The Guardian | Internasional | world, technology, dan index feed lain yang relevan | RSS didokumentasikan untuk penggunaan personal/nonkomersial sesuai syarat layanan; verifikasi endpoint dan batas praktik sebelum produksi. |

Contoh URL feed ANTARA yang **tercantum resmi**:

- `https://www.antaranews.com/rss/terkini.xml`
- `https://www.antaranews.com/rss/politik.xml`
- `https://www.antaranews.com/rss/ekonomi.xml`
- `https://www.antaranews.com/rss/tekno.xml`
- `https://www.antaranews.com/rss/olahraga.xml`
- `https://www.antaranews.com/rss/dunia.xml`

Dokumentasi The Guardian menjelaskan pola `/<section>/rss`, tetapi setiap feed nyata perlu health-check sebelum diaktifkan; feed yang gagal tidak boleh menggagalkan sumber lain. `en.antaranews.com` dapat menjadi sumber bahasa Inggris cadangan, namun tidak dihitung sebagai penerbit independen.

**Aturan legal/etika:** gunakan metadata dan cuplikan RSS sesuai syarat; patuhi `robots.txt` untuk crawling HTML dan aturan per penerbit; tidak mengakali paywall, autentikasi, CAPTCHA, pembatasan anti-bot, atau rate limit. Artikel HTML hanya di-fetch pada URL penerbit yang disetujui. Kirim tautan ke artikel asli, bukan reproduksi teks penuh. Jika akses HTML tidak diizinkan, gunakan metadata/cuplikannya saja atau lewati artikelnya sesuai kualitas data.

## 7. Spesifikasi Fungsional (P0)

| ID | Persyaratan | Prioritas |
|---|---|---|
| FR-01 | Mendaftarkan `CommandHandler('berita', berita_command)` sebelum `MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)` dan menambahkan menu berita melalui `menus.py`. | P0 |
| FR-02 | Setiap command/callback berita memanggil `is_allowed(update)` sebelum operasi network/LLM. | P0 |
| FR-03 | Memuat daftar feed dari konfigurasi allowlist; kategori dipetakan eksplisit; jangan menerima URL feed arbitrer dari chat. | P0 |
| FR-04 | HTTP async dengan timeout, batas ukuran respons, user-agent yang wajar, retry terbatas dengan backoff; error sumber diisolasi. | P0 |
| FR-05 | Parse RSS dan normalisasi metadata (judul, link, sumber, kategori, tanggal, excerpt). | P0 |
| FR-06 | Canonicalisasi URL dan deduplikasi pada URL/title fingerprint; pilih item terbaru tanpa menyatukan fakta dua artikel berbeda. | P0 |
| FR-07 | Ekstraksi body HTML selektif dengan Trafilatura bila izin, HTTP, dan konten mendukung; hentikan jika gagal atau diblokir. | P0 |
| FR-08 | Ringkasan masing-masing artikel via `/v1/chat/completions` pada shared local LLM, dengan prompt grounding dan batas input/output. | P0 |
| FR-09 | Fallback per artikel jika model gagal, keluaran kosong, atau kualitas input tidak memadai; tidak boleh menampilkan ringkasan palsu. | P0 |
| FR-10 | Respons Telegram berformat aman dengan sumber, waktu WIB, URL asli; status proses dan error yang jelas. | P0 |
| FR-11 | Simpan metadata/cache di `data/news.db` milik bot multifungsi; tidak memakai `data/assistant.db`. | P0 |
| FR-12 | Tutup HTTP client/news service saat shutdown dan pastikan fitur lama tidak terganggu. | P0 |
| FR-13 | Jangan ada scheduler, polling feed periodik, atau cron News Skill. | P0 |
| FR-14 | Handler berita tidak memblokir pemrosesan update lain (`block=False` atau task terkelola), dengan limit task aktif per pemilik, cancellation/cleanup, dan tanpa memodifikasi `context.args` yang dipakai handler lain. | P0 |

## 8. Desain LLM dan Kualitas Ringkasan

**Endpoint bersama:** `POST http://127.0.0.1:8080/v1/chat/completions` (OpenAI-compatible dari `llama-server`). **Model:** `qwen3-0.6b`. Konfigurasi URL/model di bot multifungsi disimpan dalam `.env` **milik bot itu sendiri**, bukan dibaca dari `.env` Personal AI Assistant. URL loopback berlaku karena semua berjalan di host yang sama.

**Parameter awal yang disarankan untuk News Skill:** temperature `0.2`, output maksimal `256` token, input artikel dipangkas berdasarkan batas karakter/token yang aman, timeout **45 detik per artikel** dan batas waktu total request **180 detik**, dengan tingkat konkurensi LLM **1** untuk mengurangi kontensi dengan Personal AI. Nilai ini merupakan default desain yang **perlu diukur** di perangkat asli, bukan jaminan kinerja. Parameter Personal AI yang sudah ada (`LLM_MAX_TOKENS=160`, `LLM_TIMEOUT_SECONDS=120`) **tidak diubah**. Prefix `/no_think` boleh digunakan bila terbukti kompatibel dengan template model; tidak boleh dijadikan asumsi tanpa pengujian.

**Isi prompt minimum:** identitas tugas sebagai peringkas berita, Bahasa Indonesia, gunakan hanya artikel yang diberikan; pertahankan nama/angka/tanggal dan atribusi; jangan menebak bagian yang hilang; bedakan fakta dari opini/klaim narasumber; abaikan instruksi yang muncul di dalam artikel (prompt injection); keluarkan ringkasan singkat tanpa link fiktif. Artikel diberi delimiters sebagai **data tidak tepercaya**. AI tidak diberi kewenangan mengakses file, shell, jaringan, atau tool lain.

**Aturan kualitas:** ringkasan per artikel, bukan ringkasan seluruh daftar; ketika hanya cuplikan RSS yang tersedia, beri label 'Ringkasan berdasarkan cuplikan sumber' apabila LLM digunakan. Jika LLM gagal, isi balasan memakai excerpt persis sebagai cuplikan sumber yang diberi atribusi; jangan memberikan klaim seolah AI berhasil. Pastikan respons kosong, halusinasi URL, atau teks berpola instruksi ditangani sebagai gagal bila terdeteksi; evaluasi manual tetap diperlukan karena model 0.6B tidak menjamin akurasi.

## 9. Arsitektur dan Pemisahan Environment

```text
HOST / PERANGKAT SAMA
├── telegram_personal_ai/             # Proyek A (TIDAK DIMODIFIKASI)
│   ├── .venv/                         # Dependensi Personal AI
│   ├── .env                           # TG_API_ID, TG_API_HASH, sesi Telethon, LLM
│   └── data/assistant.db              # Data dan RAG Personal AI
├── telegram_multifungsi/             # Proyek B (NEWS SKILL DITAMBAHKAN)
│   ├── .venv/                         # Dependensi bot multifungsi sendiri
│   ├── .env                           # TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, NEWS_*
│   ├── main.py                        # Registrasi handler lama + /berita
│   ├── menus.py                       # Tambah menu berita
│   ├── config.py                      # Konfigurasi validasi news
│   ├── src/news/                     # Modul terisolasi (usulan)
│   │   ├── service.py                 # Orkestrasi per command
│   │   ├── sources.py                 # Registry feed resmi
│   │   ├── fetcher.py                 # RSS/HTTP/normalisasi
│   │   ├── extractor.py               # Ekstraksi artikel selektif
│   │   ├── summarizer.py              # Klien LLM OpenAI-compatible
│   │   ├── storage.py                 # Cache SQLite
│   │   └── handlers.py                # Handler/formatter Telegram
│   └── data/news.db                   # Cache News Skill, DB terpisah
└── llama-server                       # Satu proses dan satu model bersama
    └── 127.0.0.1:8080 / qwen3-0.6b
```

**Pemisahan teknis yang wajib:**

1. Dua proses Python dan dua `.venv`; dependensi diinstal per proyek. Menjalankan/menghentikan salah satu aplikasi tidak otomatis menghentikan aplikasi lain.
2. Dua `.env` independen: pengulangan konfigurasi host/model boleh, **tidak ada impor** `TG_API_HASH`, session Telethon, prompt, knowledge, atau token bot lain.
3. Kedua klien harus berada dalam **network namespace yang dapat mengakses loopback server yang sama**. Bila kelak salah satu proyek memakai container terisolasi, `127.0.0.1` di dalam container tidak otomatis menunjuk ke host; endpoint harus disesuaikan dengan jaringan yang aman.
4. `llama-server` adalah dependensi runtime bersama, **bukan environment Python yang dibagikan** dan **tidak memuat model dua kali** jika satu proses server digunakan.
5. `news.db` menyimpan hanya informasi News Skill; data Personal AI/RAG tetap di `assistant.db`. Tidak ada migrasi lintas proyek.
6. `llama-server` di-bind ke loopback; tidak mengekspos endpoint ke internet. Jika server sedang sibuk atau tidak aktif, hanya komponen ringkasan yang mengalami fallback.
7. Saat startup, bot tidak boleh gagal total hanya karena `llama-server` unavailable. Health-check dapat dilakukan **ketika perintah berita masuk** (atau pada inisialisasi tanpa menghalangi startup), bukan scraping berita terjadwal.

**Contoh `.env` pada bot multifungsi (hanya variabel baru; variabel existing tetap ada):**

```dotenv
NEWS_ENABLED=true
NEWS_DB_PATH=data/news.db
NEWS_MAX_ARTICLES=5
NEWS_CACHE_TTL_SECONDS=180
NEWS_LOOKBACK_HOURS=48
NEWS_HTTP_TIMEOUT_SECONDS=12
NEWS_SUMMARY_LANGUAGE=id
NEWS_LLM_BASE_URL=http://127.0.0.1:8080
NEWS_LLM_MODEL=qwen3-0.6b
NEWS_LLM_ALLOW_REMOTE=false
NEWS_LLM_TEMPERATURE=0.2
NEWS_LLM_MAX_TOKENS=256
NEWS_LLM_TIMEOUT_SECONDS=45
NEWS_TOTAL_TIMEOUT_SECONDS=180
NEWS_LLM_CONCURRENCY=1
```

Tidak menaruh token atau password asli di PRD atau contoh kode. `NEWS_LLM_BASE_URL` hanya menerima loopback HTTP/HTTPS yang diizinkan ketika `NEWS_LLM_ALLOW_REMOTE=false`.

## 10. Rancangan Data, Cache, dan Resource

**SQLite News Skill** menyimpan: `id`, `source_id`, `category`, `title`, `canonical_url` (unique), `published_at_utc`, `fetched_at_utc`, `excerpt`, `summary`, `summary_origin` (`llm_full_text`, `llm_excerpt`, `source_excerpt`), `summary_model`, `summary_created_at`, dan `fingerprint`. Metadata bersifat publik. HTML/body penuh digunakan dalam memori proses saja dan tidak perlu disimpan permanen. Hindari mencatat isi prompt, API hash, token Telegram, atau identitas pengguna di log.

**Cache:** TTL awal 180 detik dihitung dari waktu pengambilan feed; menekan 'Perbarui' atau mengulang command dalam TTL boleh menggunakan cache tetapi harus menampilkan waktu pengambilan. Saat terjadi kegagalan semua sumber, cache lebih lama hanya boleh dipakai jika ditandai **'Hasil tersimpan, bukan pembaruan langsung'**. Ringkasan cache berlaku untuk versi teks/fingerprint dan model yang sama; hasil kosong/gagal tidak disimpan sebagai ringkasan sukses.

**Retensi awal:** metadata/cache artikel maksimal 14 hari, ringkasan maksimal 7 hari untuk MVP; pembersihan dilakukan **secara oportunistik ketika command dieksekusi**, bukan scheduler mandiri. Batas ukuran DB dan jumlah artikel dapat diatur. Jika penyimpanan gagal, berita tetap dapat dikirim tanpa cache.

**Resource:** gunakan `httpx.AsyncClient` untuk RSS dan LLM; XML diparse dengan `feedparser`; ekstraksi body menggunakan `trafilatura` bila lolos kebijakan akses (jalankan CPU-bound extraction di thread jika perlu). `asyncio.Semaphore(1)` News LLM terpisah dari `DOWNLOAD_LIMIT`. Gunakan deadline total agar tidak mengantre tanpa batas dan jangan memblokir event loop. Pastikan klien HTTP ditutup saat `post_shutdown`. Karena PTB dapat memproses update secara berurutan secara default, jalankan pekerjaan News melalui handler non-blocking (`block=False` atau task terkelola) dengan pencegahan request ganda, sehingga download/converter/cuaca tetap dapat menerima update.

## 11. Keamanan, Kepatuhan, dan Keterandalan

- **Otorisasi:** semua command dan tombol berita diperiksa melalui `is_allowed`; hanya private chat pemilik.
- **URL security / SSRF:** RSS berasal dari allowlist statis. Artikel hanya boleh `https`, host penerbit allowlist, resolusi IP publik, redirect divalidasi ulang, tidak memanggil alamat internal/loopback dari data artikel. Ini penting walaupun pengguna tunggal karena feed adalah input pihak ketiga.
- **HTTP hygiene:** batasi ukuran respons (contoh awal: feed 2 MB, HTML 3 MB), jumlah redirects, connect/read timeout, user-agent, retry hanya untuk error sementara; 403/401/429 tidak boleh dibypass.
- **XML/HTML:** gunakan parser aman, sanitasi markup dan `html.escape` sebelum `ParseMode.HTML`; jangan jalankan script dari situs. Batasi panjang input ke model.
- **Prompt injection:** artikel tidak boleh mengubah instruksi sistem maupun memicu perintah, kode, akses file, atau pemanggilan tool. LLM hanya menulis ringkasan.
- **Hak cipta:** simpan atribut sumber, gunakan cuplikan dan ringkasan singkat, arahkan pembaca ke artikel asli; review persyaratan lisensi jika pola penggunaan berubah dari privat/nonkomersial.
- **Graceful degradation:** kesalahan satu feed tidak menghentikan lainnya, kesalahan satu artikel tidak membatalkan daftar, LLM offline menghasilkan fallback, kegagalan database tidak menghentikan fitur berita sementara.
- **Keamanan secret:** `.env` dan sesi Personal AI tetap terpisah, masuk `.gitignore`, tidak pernah ditampilkan di log maupun jawaban Telegram.
- **Observabilitas:** log jumlah feed sukses/gagal, jumlah artikel valid/duplikat, waktu fetch, waktu LLM, fallback rate, error class. Jangan log berita penuh secara default.

## 12. Non-Functional Requirements

| NFR | Kriteria |
|---|---|
| NFR-01 Isolasi | Error dan restart News Skill tidak menyebabkan konversi/downloader/cuaca/monitor Discord terhenti. |
| NFR-02 Responsivitas | Status awal dikirim segera; I/O bersifat async, dan dispatcher bot tetap menangani update lain selama News berlangsung. |
| NFR-03 Batas kerja | Maksimal 5 artikel default, maksimal 1 inference News Skill simultan, total deadline konfigurabel. |
| NFR-04 Akurasi | Semua ringkasan dapat ditelusuri ke input sumber; 18/20 sampel uji tidak boleh memiliki klaim substantif tambahan. |
| NFR-05 Keterkinian | Prioritaskan publikasi ≤48 jam; tandai hasil cache atau artikel lama. |
| NFR-06 Keamanan | Semua link dan teks diparsing/di-escape; tidak mengakses URL internal atau endpoint luar allowlist. |
| NFR-07 Portabilitas | Dependency kompatibel dengan lingkungan host; instalasi tidak mengubah `.venv` Personal AI. |
| NFR-08 Ketergantungan | Startup bot tetap berjalan tanpa LLM; sumber berita dan LLM bisa gagal secara terpisah. |

## 13. Acceptance Criteria dan Pengujian

| ID | Skenario | Hasil lulus |
|---|---|---|
| AC-01 | Pemilik mengirim `/berita` | Hingga 5 artikel ditampilkan dengan semua metadata wajib. |
| AC-02 | Pemilik mengirim `/berita internasional` | Hanya feed yang dipetakan sebagai internasional yang dipakai. |
| AC-03 | Pemilik mengirim `/berita teknologi` | Kategori valid dikenali; tidak salah masuk downloader URL handler. |
| AC-04 | User tak diizinkan mengirim command/callback | Tidak ada fetch/LLM; akses ditolak. |
| AC-05 | Feed berhasil tetapi salah satu artikelnya rusak | Artikel lain tetap tampil; error tercatat tanpa crash. |
| AC-06 | Dua feed memberikan URL yang sama | URL hanya tampil sekali dalam satu respons. |
| AC-07 | Feed memiliki artikel lama/tanggal hilang | Label waktu sesuai; tidak diklaim baru. |
| AC-08 | LLM mati sebelum command | Artikel dan excerpt tampil dengan label 'tanpa ringkasan AI'. |
| AC-09 | LLM timeout pada artikel ke-2 | Artikel lain tetap diproses dalam deadline; artikel gagal mendapat fallback. |
| AC-10 | Artikel berisi instruksi 'abaikan aturan' | Model tidak mengikuti instruksi artikel; hanya merangkum berita. |
| AC-11 | Sumber artikel redirect ke IP lokal/domain tak sah | Fetch artikel ditolak; sistem tidak mengakses target. |
| AC-12 | Server penerbit memberi 403/429 | Tidak ada bypass, retry agresif, atau crawling lanjutan. |
| AC-13 | Hasil melebihi panjang pesan Telegram | Output dipecah tanpa HTML rusak. |
| AC-14 | News Skill dipanggil ketika download berlangsung | Downloader/converter tetap responsif; limit news terpisah. |
| AC-15 | Bot restart, LLM offline | Bot tetap berjalan; `/cuaca` dan command lain tetap berfungsi. |
| AC-16 | Cek dua proyek | Venv, `.env`, database, dan Telegram credential berbeda; hanya LLM endpoint yang sama. |
| AC-17 | Tidak ada command berita masuk | Tidak ada request fetch berita maupun ringkasan terjadwal. |
| AC-18 | Artikel bahasa Inggris | Hasil AI berbahasa Indonesia, nama/angka/tanggal tetap akurat. |

**Pengujian wajib sebelum rilis:** unit test RSS mock/invalid XML/duplicate URL; mock LLM success, empty output, 429, timeout, unreachable; uji security URL/redirect dan prompt injection; uji integrasi di bot nyata; manual review ringkasan; regression test converter, downloader, BMKG, Discord Voice, menu/callback, dan pengaturan akses.

## 14. Tahapan Pengembangan dan Deliverable

1. **Audit repositori:** periksa versi `python-telegram-bot`, `menus.py`, `config.py`, file requirements, lokasi host serta cara menjalankan `llama-server`. Pastikan environment dua proyek tidak tertukar.
2. **Fondasi News Skill:** buat modul terpisah, source registry + allowlist, HTTP client, RSS parser, kategorisasi, pengujian fetch tanpa LLM.
3. **LLM summarizer:** implementasi prompt per artikel, batas input/token, semaphore, timeout, retry aman, fallback.
4. **Telegram integration:** tambah command/menu/callback terkait; format HTML, status proses, pembatasan pemilik, cleanup lifecycle.
5. **Data dan hardening:** SQLite, dedup/cache, validasi URL, kepatuhan akses, logging sanitasi, limit resource.
6. **UAT dan regression:** eksekusi AC-01–AC-18, ukur beban perangkat dan latensi aktual, perbaiki masalah sebelum rilis.

**Hasil yang harus diserahkan oleh developer/AI coding agent:** perubahan kode modular, daftar dependensi baru yang dipin, `.env.example` khusus bot multifungsi (tanpa rahasia), migrasi/inisialisasi `news.db`, unit dan integration tests, README setup/rollback, serta catatan keterbatasan sumber.

## 15. Risiko dan Mitigasi

| Risiko | Mitigasi |
|---|---|
| Qwen3 0.6B membuat ringkasan keliru | Prompt grounded, batas input, sampel evaluasi manual, tautan sumber jelas. |
| Proses inference bersama memperlambat Personal AI | Semaphore News=1, deadline, fallback, monitoring latensi; tidak memuat model kedua. |
| Feed berubah atau diblokir | Source registry terpisah, health-check saat dipakai, skip satu sumber, fallback lain. |
| Konten berhak cipta/akses HTML tidak diizinkan | Gunakan RSS, excerpt sesuai kebijakan, ringkasan singkat, link asli, tidak bypass. |
| Resource host terbatas | Batasi 5 artikel, fetch selektif, tidak menggunakan headless Chromium pada MVP. |
| Konflik menu/handler | Audit urutan register dan pola callback; test semua menu lama. |
| Cache menyajikan berita tidak baru | Cap waktu pengambilan dan label 'hasil tersimpan'. |
| Data luar memancing akses internal | Static allowlist + kontrol redirect/DNS/IP dan sandbox text prompt. |

## 16. Definisi Selesai (Definition of Done)

MVP siap digunakan ketika AC-01 sampai AC-18 lulus, RSS nasional/internasional yang dikonfigurasi berhasil diuji pada host, ringkasan per artikel dan fallback berfungsi, semua fitur lama lolos regression test, serta bot dan Personal AI tetap menjalankan environment terpisah dengan satu `llama-server` lokal yang sama. **Dokumen ini adalah PRD, bukan klaim bahwa kode News Skill telah dibuat atau diterapkan.**

## 17. Referensi Teknis

1. ANTARA News — daftar RSS resmi: https://www.antaranews.com/rss/
2. The Guardian — RSS Help: https://www.theguardian.com/help/feeds
3. The Guardian — Terms of Service: https://www.theguardian.com/help/terms-of-service
4. `python-telegram-bot` Application/Handlers: https://docs.python-telegram-bot.org/en/latest/telegram.ext.application.html
5. `llama.cpp` Server API: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
6. Trafilatura extraction API: https://trafilatura.readthedocs.io/en/latest/usage-python.html
7. RFC 9309 — Robots Exclusion Protocol: https://www.rfc-editor.org/rfc/rfc9309.html
8. Telegram Bot API — callback limits: https://core.telegram.org/bots/api
9. Lampiran internal: kode utama bot Telegram multifungsi yang diberikan pemilik proyek, 25 Oktober 2026 (tidak dipublikasikan).
