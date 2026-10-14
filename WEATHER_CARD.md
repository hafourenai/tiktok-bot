# Upgrade Kartu Cuaca BMKG

## Perubahan yang Dilakukan

### 1. Format Portrait Mobile-Friendly
- Ubah dimensi dari **1000×650px** (landscape) ke **1080×1350px** (portrait)
- Optimal untuk ditampilkan di layar HP tanpa perlu cropping

### 2. Tema Otomatis Malam/Siang
- Deteksi waktu lokal (18:00-06:00 = malam)
- Tema malam lebih gelap dengan aksen yang lebih lembut
- Tema siang lebih cerah dengan gradien yang berwarna

### 3. Layout yang Lebih Rapi
- **Header**: Badge BMKG + waktu saat ini
- **Lokasi**: Nama desa, kecamatan, kota/kabupaten, provinsi
- **Hero Section**: Ikon cuaca besar + suhu + deskripsi cuaca
- **Metrics**: 3 indikator (kelembapan, angin, zona waktu) dalam grid
- **Prakiraan**: 4 kartu timeline periode berikutnya
- **Ringkasan Harian**: 3 hari dengan rentang suhu dan kondisi
- **Footer**: Sumber data dan attribution

### 4. Visual Improvements
- Gradient background yang halus sesuai kondisi cuaca
- Efek glass frosted pada kartu dan box
- Ambient glow untuk kedalaman visual
- Ikon vektor yang lebih besar dan jelas

### 5. Bersihkan File React
- Hapus folder `src/react/` (tidak diperlukan untuk bot Telegram)
- Hapus `REACT_SETUP.md`, `WEATHER_COMPONENTS_SUMMARY.md`, `setup-react.sh`
- Tetahankan `package.json` untuk downloader TikTok/Instagram

## Format Data yang Dihasilkan

Kartu dihasilkan sebagai **JPEG 1080×1350px** dengan kualitas 92%, optimized untuk:
- Ukuran file relatif kecil (~80-120KB)
- Kecepatan rendering cepat di Pillow
- Kompatibel dengan Termux

## Testing

Coba jalankan test:
```bash
cd ~/bot_honey
python -m pytest tests/test_weather_card.py -v
```

Atau jalankan tes manual:
```python
from weather_card import generate_weather_card
from datetime import datetime, timezone

# Mock data
forecast = {"lokasi": {...}, "data": [...]}
card = generate_weather_card(forecast, "31.71.03.1001")

# Save to file
with open("weather.jpg", "wb") as f:
    f.write(card.read())
```

## Integrasi dengan Bot

Bot sudah menggunakan `generate_weather_card()` di handler cuaca:
- `/cuaca` (GPS) → `handle_weather_location()`
- `/cuaca_manual` (manual region) → `weather_region_callback()`

Kedua handler sudah memanggil `generate_weather_card()` dan mengirim gambar via `reply_photo()`.

## Notes untuk Termux

- Memerlukan `Pillow >= 10.0.0` (sudah di requirements.txt)
- Font fallback ke system fonts Android jika font lokal tidak ada
- Rendering ~500ms per kartu (acceptable untuk Telegram)
