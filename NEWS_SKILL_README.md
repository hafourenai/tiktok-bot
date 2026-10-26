## News Skill — Setup & Dokumentasi

### Instalasi Dependencies

News Skill memerlukan library tambahan:

```bash
python -m pip install feedparser trafilatura
```

Atau jalankan dari direktori bot:
```bash
python -m pip install -r requirements.txt
```

### Konfigurasi `.env`

Salin `.env.example` dan isi bagian News Skill:

```dotenv
# News Skill — Aktifkan/nonaktifkan
NEWS_ENABLED=true

# Database cache
NEWS_DB_PATH=data/news.db

# Fetch parameters
NEWS_MAX_ARTICLES=5
NEWS_CACHE_TTL_SECONDS=180
NEWS_LOOKBACK_HOURS=48
NEWS_HTTP_TIMEOUT_SECONDS=12
NEWS_EXTRACT_TIMEOUT_SECONDS=15

# LLM integration (shared dengan host yang sama)
NEWS_LLM_BASE_URL=http://127.0.0.1:8080
NEWS_LLM_MODEL=qwen3-0.6b
NEWS_LLM_ALLOW_REMOTE=false
NEWS_LLM_TEMPERATURE=0.2
NEWS_LLM_MAX_TOKENS=120
NEWS_LLM_TIMEOUT_SECONDS=45
NEWS_TOTAL_TIMEOUT_SECONDS=180
NEWS_LLM_CONCURRENCY=1
NEWS_LLM_CONTEXT_TOKENS=1024
NEWS_LLM_HEALTH_TIMEOUT_SECONDS=2
NEWS_LLM_COOLDOWN_SECONDS=300
NEWS_SUMMARY_MODE=auto
NEWS_EXTRACTIVE_MAX_SENTENCES=2
NEWS_EXTRACTIVE_MAX_WORDS=60
```

### Requirements untuk LLM

- Jalankan `llama-server` dengan model `qwen3-0.6b` di `http://127.0.0.1:8080`
- Server harus support endpoint `/v1/chat/completions` (OpenAI-compatible)

Contoh menjalankan llama-server:
```bash
./llama-server -m qwen3-0.6b.gguf --host 127.0.0.1 --port 8080 --ctx-size 4096
```

Jika memakai `--ctx-size 4096`, ubah `NEWS_LLM_CONTEXT_TOKENS=4096` agar bot
dapat memanfaatkan konteks tersebut. Mode `auto` memeriksa kesehatan LLM dalam
2 detik. Ketika server mati atau timeout, bot langsung memakai ringkasan
penerbit atau ringkasan ekstraktif tanpa AI selama masa cooldown.

### Command Penggunaan

User hanya perlu menjalankan perintah di Telegram:

```
/berita                    # Berita semua kategori
/berita nasional           # Hanya berita nasional
/berita internasional      # Hanya berita internasional
/berita teknologi          # Berita teknologi
/berita ekonomi            # Berita ekonomi
/berita politik            # Berita politik
/berita olahraga           # Berita olahraga
```

### Fitur

✅ **Fetch RSS otomatis** dari ANTARA, CNN Indonesia, dan The Guardian
✅ **Deduplicasi artikel** berdasarkan URL dan fingerprint
✅ **Ekstraksi konten full-text** menggunakan Trafilatura (opsional)
✅ **Summarisasi AI per artikel** dengan prompt grounded menggunakan Qwen3 0.6B
✅ **Fallback deterministik** dari deskripsi penerbit atau kalimat artikel jika LLM gagal
✅ **Health gate dan cooldown** agar LLM mati tidak memperlambat setiap artikel
✅ **Cache SQLite** dengan TTL dan retensi
✅ **HTML-safe output** dengan message splitting untuk Telegram
✅ **Non-blocking handler** dengan semaphore LLM terpisah
✅ **Security validation** untuk URL (HTTPS, allowlist, no SSRF)

### Struktur Modul

```
src/news/
├── __init__.py           # Package init
├── models.py             # Dataclass Article, NewsResult, ArticleSummary
├── sources.py            # Feed registry, category mapping, allowlist
├── fetcher.py            # RSS fetch & parse, dedup, sort
├── extractor.py          # HTML content extraction dengan Trafilatura
├── extractive.py         # Ringkasan deterministik tanpa AI
├── security.py           # URL/IP validation untuk SSRF prevention
├── summarizer.py         # LLM client (OpenAI-compatible)
├── storage.py            # SQLite cache dan metadata
├── service.py            # Main orchestration service
└── handlers.py           # Telegram command handlers
```

### Acceptance Criteria

Implementasi memenuhi PR D sebagai berikut:

| AC | Skenario | Status |
|----|----------|--------|
| AC-01 | `/berita` menampilkan hingga 5 artikel | ✅ Implemented |
| AC-02 | `/berita internasional` hanya feed internasional | ✅ Implemented |
| AC-03 | Kategori valid dikenali | ✅ Implemented |
| AC-04 | User tak diizinkan ditolak | ✅ Implemented |
| AC-05 | Artikel rusak tidak menggagalkan feed lain | ✅ Implemented |
| AC-06 | Duplicate URL dihapus | ✅ Implemented |
| AC-07 | Artikel diprioritaskan berdasarkan keterkinian | ✅ Implemented |
| AC-08 | LLM offline → ringkasan penerbit/ekstraktif | ✅ Implemented |
| AC-09 | LLM timeout per artikel, tidak membatalkan rest | ✅ Implemented |
| AC-10 | Prompt injection di artikel tidak diikuti | ✅ Implemented (prompt grounding) |
| AC-11 | Redirect ke IP lokal ditolak | ✅ Implemented (security.py) |
| AC-12 | 403/429 tidak dibypass | ✅ Implemented |
| AC-13 | Pesan panjang dipecah | ✅ Implemented |
| AC-14 | News tidak mengganggu downloader/converter | ✅ Implemented (semaphore LLM=1) |
| AC-15 | Bot/LLM offline tetap berjalan | ✅ Implemented |
| AC-16 | Environment terpisah dari Personal AI | ✅ Implemented |
| AC-17 | Tidak ada scheduler otomatis | ✅ Implemented |
| AC-18 | Output Bahasa Indonesia | ✅ Implemented |

### Testing

Unit tests tersedia di `tests/test_news.py`:

```bash
python -m pytest tests/test_news.py -v
```

Tests mencakup:
- Kategori validation
- Deduplicasi artikel
- Fingerprinting
- Storage (SQLite insert/retrieve)
- LLM prompt construction
- Ringkasan penerbit dan ekstraktif
- Pemilihan artikel seimbang per penerbit
- URL security validation
- Message splitting

### Keterbatasan & Catatan

1. **RSS Feeds hanya**: Tidak crawl website bebas, hanya allowlist RSS resmi.
2. **Ekstraksi konten**: Trafilatura membantu tapi tidak menjamin 100% sukses; deskripsi RSS penerbit diprioritaskan sebagai fallback.
3. **LLM accuracy**: Qwen3 0.6B model terbatas; evaluasi manual ringkasan sangat disarankan sebelum production.
4. **Rate limiting**: Server penerbit bisa rate limit; implementasi retry konservatif (exponential backoff).
5. **Feed URL changes**: Jika feed URL berubah, update di `sources.py` dan restart bot.
6. **Cache retention**: Metadata disimpan 14 hari, ringkasan 7 hari (oportunistik cleanup).
7. **Loopback LLM only**: Default `NEWS_LLM_ALLOW_REMOTE=false` untuk security; ubah ke `true` hanya jika benar-benar butuh remote.
8. **Kompas tidak digunakan**: robots.txt Kompas melarang pengambilan otomatis dan penggunaan konten untuk AI/LLM.

### Rollback

Untuk menghapus News Skill:

1. Set `NEWS_ENABLED=false` di `.env`
2. Jalankan bot (News commands akan tidak tersedia, fitur lain tetap jalan)
3. Hapus modul: `rm -r src/news/` (opsional; tidak mempengaruhi bot jika disabled)
4. Hapus database cache: `rm data/news.db` (opsional)

Fitur existing (downloader, converter, BMKG, Discord Voice) **tidak terpengaruh**.

### Referensi

- PRD: `PRD_News_Skill_Bot_Telegram_Multifungsi.md`
- ANTARA RSS: https://www.antaranews.com/rss/
- CNN Indonesia RSS: https://www.cnnindonesia.com/rss
- The Guardian RSS: https://www.theguardian.com/help/feeds
- Trafilatura: https://trafilatura.readthedocs.io/
- feedparser: https://feedparser.readthedocs.io/
- llama.cpp server: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
