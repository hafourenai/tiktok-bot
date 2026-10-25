# BAAK Schedule Scraper

Lightweight Python scraper untuk mengambil jadwal kuliah Universitas Gunadarma dengan bypass Cloudflare menggunakan `curl-cffi`.

## Fitur

- ✅ Parse jadwal kuliah dari BAAK dengan 7 kolom inti
- ✅ Konversi notasi jam BAAK (1-14 slot) ke waktu nyata
- ✅ Filter berdasarkan hari dan nama mata kuliah
- ✅ Caching in-memory dengan TTL 6 jam
- ✅ Fallback ke snapshot terverifikasi
- ✅ Output JSON + format tabel
- ✅ Test suite lengkap (14 slot + fixture parsing)
- ✅ Bekerja di Termux (dependensi ringan)

## Setup

### Prerequisite

- Python 3.8+
- pip

### Lokal (Windows/Mac/Linux)

```bash
# Clone/extract ke folder
cd baak-scraper

# Install dependencies
pip install -r requirements.txt

# Jalankan tests
pytest -v

# Jalankan CLI
python main.py --help
```

### Termux (Android)

```bash
# Install Python
pkg update
pkg install python

# Clone ke storage
git clone <repo> ~/baak-scraper
cd ~/baak-scraper

# Install deps
pip install -r requirements.txt

# Test
python -m pytest tests/

# Jalankan
python main.py --class 3KA01
```

## Penggunaan

### CLI Commands

```bash
# Search kelas
python main.py --class 3KA01

# Filter by day
python main.py --class 3KA01 --hari Senin

# Filter by subject
python main.py --class 3KA01 --subject "Basis Data"

# Output format table
python main.py --class 3KA01 --output table

# Force refresh (ignore cache)
python main.py --class 3KA01 --force-refresh

# Save to snapshot (setelah fetch berhasil)
python main.py --class 3KA01 --save-snapshot

# Validate all snapshots
python main.py --validate-snapshots

# Clear in-memory cache
python main.py --clear-cache

# Verbose logging
python main.py --class 3KA01 -v
```

### Python API

```python
from scraper.client import BAAKClient
from scraper.parser import BAAKParser
from scraper.converter import convert_waktu

# Fetch dari BAAK
client = BAAKClient()
html = client.get("/")

# Parse HTML
jadwal_list = BAAKParser.parse_schedule_html(html, target_kelas="3KA01")

# Sort by day then time
sorted_jadwal = BAAKParser.sort_jadwal(jadwal_list)

# Filter
senin_only = BAAKParser.filter_by_day(sorted_jadwal, "Senin")

# Convert time
jam_mulai, jam_selesai, jam_display, warnings = convert_waktu("1/2")
print(jam_display)  # "07.30–09.30 WIB"
```

## Struktur

```
baak-scraper/
├── scraper/
│   ├── client.py          # HTTP client with curl-cffi
│   ├── parser.py          # HTML parsing & filtering
│   ├── converter.py       # 14-slot time conversion
│   ├── models.py          # Dataclass (Jadwal, Response)
│   └── __init__.py
├── tests/
│   ├── test_converter.py  # 14 slot + edge cases
│   ├── test_parser.py     # Parsing & filtering
│   ├── conftest.py        # Pytest fixtures
│   ├── fixtures/
│   │   └── sample_baak.html
│   └── __init__.py
├── data/
│   └── snapshots/         # Snapshot JSON (semester_xx.json)
├── main.py                # CLI entry point
├── requirements.txt       # Dependencies
└── README_SETUP.md        # This file
```

## Waktu Kuliah (14 Slot)

| Slot | Mulai  | Selesai |
|------|--------|---------|
| 1    | 07:30  | 08:30   |
| 2    | 08:30  | 09:30   |
| 3    | 09:30  | 10:30   |
| 4    | 10:30  | 11:30   |
| 5    | 11:30  | 12:30   |
| 6    | 12:30  | 13:30   |
| 7    | 13:30  | 14:30   |
| 8    | 14:30  | 15:30   |
| 9    | 15:30  | 16:30   |
| 10   | 16:30  | 17:30   |
| 11   | 17:30  | 18:30   |
| 12   | 18:30  | 19:30   |
| 13   | 19:30  | 20:30   |
| 14   | 20:30  | 21:30   |

Contoh:
- `1` → `07.30–08.30 WIB`
- `1/2` → `07.30–09.30 WIB`
- `5/6` → `11.30–13.30 WIB`

## Output JSON Schema

```json
{
  "success": true,
  "kelas": "3KA01",
  "semester": "PTA 2026/2027",
  "data": [
    {
      "kelas": "3KA01",
      "hari": "Senin",
      "mata_kuliah": "Pemrograman Basis Data",
      "waktu": "1/2",
      "jam_mulai": "07:30",
      "jam_selesai": "09:30",
      "jam": "07.30–09.30 WIB",
      "ruang": "RUANG 101",
      "dosen": "Dr. Andi",
      "warnings": []
    }
  ],
  "meta": {
    "source_name": "BAAK Gunadarma",
    "source_url": "https://baak.gunadarma.ac.id/",
    "source_mode": "verified_snapshot",
    "fetched_at": "2026-10-25T01:23:24+07:00",
    "is_stale": false,
    "status": "ok"
  }
}
```

## Testing

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_converter.py -v

# Run with coverage
pytest --cov=scraper tests/

# Run specific test
pytest tests/test_converter.py::TestConvertWaktu::test_valid_single -v
```

### Test Coverage

- ✅ **Converter:** 14 slot satuan, rentang, invalid, edge cases
- ✅ **Parser:** ekstraksi 7 field, NA handling, day validation
- ✅ **Models:** Jadwal dan Response serialization
- ✅ **Filtering:** by day, by subject (case-insensitive)
- ✅ **Sorting:** cronologis (hari → jam)

## Snapshot Format

File: `data/snapshots/PTA_2026_2027.json`

```json
{
  "schema_version": "1.0",
  "semester": "PTA 2026/2027",
  "source_mode": "verified_snapshot",
  "source_url": "https://baak.gunadarma.ac.id/",
  "fetched_at": "2026-10-24T09:00:00+07:00",
  "jadwal": [
    { /* Jadwal entries */ }
  ]
}
```

**Kapan gunakan snapshot:**
- Sumber BAAK tidak dapat diakses
- Cloudflare challenge gagal
- Fallback untuk reliability

## Troubleshooting

### curl-cffi not installed
```
pip install curl-cffi
```

### Cloudflare blocked
- Scraper sudah handle TLS fingerprint Chrome 120
- Jika masih gagal: dokumentasi di `docs/baak-source-validation.md`
- Fallback: gunakan snapshot terverifikasi

### No schedule found
- Pastikan kode kelas benar (case-insensitive)
- Cek semester yang dipilih
- Verifikasi snapshot ada: `python main.py --validate-snapshots`

### Snapshot invalid
```bash
python main.py --validate-snapshots
```

Pastikan format JSON sesuai schema.

## Next Steps

**Phase 1 (Current):** ✅ Python scraper + tests lokal

**Phase 2 (Future):** Go REST API backend
- Endpoint: `GET /api/v1/jadwal?kelas=3KA01`
- Deploy ke Vercel
- CORS untuk website publik

**Phase 3 (Future):** Website publik
- Tanpa login
- Responsif mobile/desktop
- Search + filter UI

**Phase 4 (Future):** Integrasi Telegram
- `/jadwal <KELAS>` di Saved Messages
- Owner-only command
- Natural language support (Phase 1)

## References

- BAAK Gunadarma: https://baak.gunadarma.ac.id/
- Jadwal kuliah slots: https://baak.gunadarma.ac.id/kuliahUjian/5
- curl-cffi: https://github.com/yifeikong/curl_cffi

## License

MIT (sesuai konteks Gunadarma academic project)
