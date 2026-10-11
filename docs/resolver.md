# BMKG Location Resolver

Package Python async untuk koordinat Indonesia → wilayah administratif → prakiraan
resmi BMKG. Package inti tidak membutuhkan Telegram, Discord, Node.js, token bot,
atau `.env`. Versi awal: 0.1.0; belum dipublikasikan di PyPI.

## Instalasi

Dari root repository:

```sh
python -m pip install .
```

Untuk pengembangan gunakan `python -m pip install -e ".[dev]"`.
Untuk memasang seluruh dependensi aplikasi bot gunakan
`python -m pip install -r requirements.txt` dari root repository.

## API

```python
import asyncio
from bmkg_location_resolver import BMKGWeatherResolver, RegionSelectionRequired

async def main():
    resolver = BMKGWeatherResolver()
    try:
        result = await resolver.from_coordinates(-6.16472, 106.84538)
        print(result.code)
        print(result.location["desa"])
        print(result.html)
        # result.data berisi respons BMKG terverifikasi.
    except RegionSelectionRequired as error:
        # Tampilkan pilihan ke pengguna; jangan pilih kandidat secara otomatis.
        print(error.selected)
        print(error.candidates)

asyncio.run(main())
```

Simpan satu instance resolver per aplikasi/event loop agar pembatasan permintaan berlaku.
`forecast(lat, lon)` mengembalikan HTML untuk integrasi lama.
`regions(level, parent_code)` mengembalikan daftar wilayah tingkat 1–4.
`forecast_for_regions(selected)` menerima empat dictionary `code`/`name`
berurutan dari provinsi sampai kelurahan/desa dan mengembalikan HTML prakiraan.
Kesalahan provider/validasi memakai `WeatherError`.

Adapter Telegram opsional tanpa dependency SDK:

```python
from bmkg_location_resolver.telegram import coordinates_from_message

# message adalah objek Message Telegram (location atau venue).
coordinates = coordinates_from_message(message)
```

## Sumber dan batasan

- Cuaca: [BMKG](https://data.bmkg.go.id/prakiraan-cuaca/), prakiraan wilayah hingga
  3 hari. Bukan pengamatan real-time; tidak menjamin ketepatan setiap titik GPS.
- Kode administratif: [Wilayah.id](https://wilayah.id).
- GPS: [OpenStreetMap](https://www.openstreetmap.org/copyright)/Nominatim.
  Patuhi [usage policy](https://operations.osmfoundation.org/policies/nominatim/):
  maksimum gabungan 1 request/detik, lookup atas permintaan pengguna, atribusi,
  dan User-Agent aplikasi. Resolver membatasi permintaan per instance 1,1 detik.
  Jangan gunakan beberapa instance untuk melewati batas provider.
  Endpoint dapat diganti melalui argumen `geocoder_url`.
- Koordinat diteruskan ke geocoder; package tidak menyimpan/cache koordinat.
- Pemetaan menggunakan objek terdekat, bukan verifikasi batas poligon. Nama level
  yang hilang/tidak cocok menghasilkan `RegionSelectionRequired`, berisi wilayah
  induk yang sudah cocok dan daftar anaknya. Daftar ini bukan klaim kandidat terdekat.
- Identitas dan kesegaran prakiraan BMKG tetap divalidasi sebelum ditampilkan.

## Build dan verifikasi

```sh
python -m pip install -e ".[dev]"
python -m build
python -m pip install dist/bmkg_location_resolver-0.1.0-py3-none-any.whl
```

Wheel hanya berisi package di `src/`, bukan `.env`, database, unduhan atau kode bot.
Tes seluruh repository memerlukan dependensi bot: `pip install -r requirements.txt`.
Jalankan `python -m pytest -q`. Publikasi PyPI memerlukan akun, pemeriksaan nama
tersedia, serta keputusan lisensi dari pemilik repository; belum dilakukan.
