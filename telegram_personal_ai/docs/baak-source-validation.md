# BAAK Source Validation

**Tanggal riset:** 24 Oktober 2026  
**Ditulis oleh:** AI coding agent (Fase 0B PRD)

---

## Ringkasan Eksekutif

| Domain | Status | Keterangan |
|--------|--------|------------|
| `baak.gunadarma.ac.id` | ❌ **403 Forbidden** | Diblokir dari non-browser (semua endpoint) |
| `devel.baak.gunadarma.ac.id` | ⚠️ **Partially Accessible** | Bisa diakses tapi SSL self-signed, tidak ada jadwal per kelas |

**Kesimpulan:** Tidak ada endpoint publik yang mengembalikan jadwal kuliah lengkap per kelas (Hari, Waktu/Jam, Ruang, Dosen, Mata Kuliah) dalam format yang bisa di-scrape secara andal.

**Strategi yang dipilih: `verified_snapshot`**

---

## 1. `baak.gunadarma.ac.id` (Produksi)

### Hasil Test

```
GET https://baak.gunadarma.ac.id/             → 403 Forbidden
GET https://baak.gunadarma.ac.id/kuliahUjian/5 → 403 Forbidden
GET https://baak.gunadarma.ac.id/kuliahUjian/cariJadKul → 403 Forbidden
```

Ditest dengan:
- Tanpa User-Agent
- User-Agent Chrome 120 (`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36`)

**Semua request diblokir dengan HTTP 403.** Kemungkinan proteksi server-side (IP filtering / Cloudflare / WAF) yang memblokir request non-browser.

---

## 2. `devel.baak.gunadarma.ac.id` (Development/Staging)

### Akses

- Status: **HTTP 200** bisa diakses
- Catatan: SSL certificate self-signed → perlu skip verifikasi TLS
- Semester aktif yang terdeteksi: **PTA 2026/2027** (dari konten halaman)

### Peta Endpoint

| URL | Konten |
|-----|--------|
| `/kuliahUjian/1` | Kalender Akademik (teks informatif) |
| `/kuliahUjian/2` | Daftar Mata Kuliah (link PDF per jurusan) |
| `/kuliahUjian/3` | Daftar Dosen Wali Kelas |
| `/kuliahUjian/3?search_wali=3KA01` | Filter wali → **No \| Kelas \| Dosen** (hanya 2 kolom) |
| `/kuliahUjian/3/1` s/d `/3/5` | Daftar wali per kelompok kelas |
| `/kuliahUjian/4` | Koordinator Mata Kuliah |
| `/kuliahUjian/4?search_koor=3KA01` | Filter koor → **No \| Mata Kuliah \| Kelas \| Dosen** |
| `/kuliahUjian/5` | Daftar Dosen Pembimbing PI (Penulisan Ilmiah) |
| `/kuliahUjian/6` | **Jadwal Kuliah** — hanya teks penjelasan + tabel 14 slot jam |
| `/kuliahUjian/7` | Jadwal Ujian |
| `/kuliahUjian/cariJadKul` | Halaman cari jadwal — tidak ada data per kelas |

### Temuan Kritis: Tidak Ada Data Jadwal Per Kelas

Halaman `/kuliahUjian/6` hanya berisi:
- Penjelasan teks tentang jadwal kuliah
- Tabel 14 slot jam (informatif)
- Contoh cara membaca jadwal

**Tidak ada** tabel/form/endpoint yang mengembalikan data jadwal per kelas dengan kolom:
`Hari | Waktu/Jam | Mata Kuliah | Ruang | Dosen`

Endpoint `/kuliahUjian/cariJadKul` menampilkan:
1. Tabel Dosen Wali (No, Kelas, Dosen) — **0 baris** saat tanpa filter
2. Tabel Koordinator Mata Kuliah (No, Mata Kuliah, Kelas, Dosen) — 770 records
3. Tabel Dosen Pembimbing PI — 3.323 records
4. Tabel 14 slot jam — informatif

### Contoh Data yang Berhasil Diambil

**Dosen Wali (search `3KA01`):**
```
No | Kelas | Dosen
1  | 3KA01 | FENNI AGUSTINA
```

**Koordinator Mata Kuliah (halaman 1):**
```
No | Mata Kuliah                        | Kelas | Dosen
1  | Adm. Kontrak & Anggaran Borongan * | 4TA   | KARTINI HALIEF
2  | Agroecoturism & Pertanian Terpadu**| 3IE   | HERIK SUGERU
```

**Ini bukan jadwal kuliah (tidak ada Hari, Waktu, Ruang).**

### Tabel 14 Slot Jam (Terverifikasi dari Sumber)

Berhasil diambil langsung dari HTML halaman:

| Jam ke- | Mulai | Selesai |
|--------:|:-----:|:-------:|
| 1  | 07.30 | 08.30 |
| 2  | 08.30 | 09.30 |
| 3  | 09.30 | 10.30 |
| 4  | 10.30 | 11.30 |
| 5  | 11.30 | 12.30 |
| 6  | 12.30 | 13.30 |
| 7  | 13.30 | 14.30 |
| 8  | 14.30 | 15.30 |
| 9  | 15.30 | 16.30 |
| 10 | 16.30 | 17.30 |
| 11 | 17.30 | 18.30 |
| 12 | 18.30 | 19.30 |
| 13 | 19.30 | 20.30 |
| 14 | 20.30 | 21.30 |

Sumber: `https://devel.baak.gunadarma.ac.id/kuliahUjian/4` (section Jadwal Kuliah)  
Diverifikasi: 24 Oktober 2026 ✅

### Contoh Format Jadwal (dari teks halaman)

```
Selasa   1/2/3   E 341   Pemrograman Komputer
Rabu     5/6     D424    S I M
```

Berarti:
- `1/2/3` = Selasa jam 07.30–10.30 di Kampus E gedung 3 lantai 4 ruang 1
- `5/6` = Rabu jam 11.30–13.30 di Kampus D gedung 4 lantai 2 ruang 4

**Format yang dipakai BAAK:** `Hari | Waktu(slot) | Ruang | Mata Kuliah`

---

## 3. Kendala dan Blocker

| Kendala | Dampak |
|---------|--------|
| `baak.gunadarma.ac.id` blokir 403 | Tidak bisa scrape endpoint produksi |
| `devel.baak.gunadarma.ac.id` SSL self-signed | Perlu skip TLS; tidak cocok untuk Vercel tanpa workaround |
| Jadwal per kelas tidak tersedia sebagai endpoint terstruktur | Tidak ada API/tabel yang bisa di-parse per kelas |
| Data jadwal kemungkinan hanya di file PDF atau ditempel fisik | Tidak ada bukti endpoint HTML dengan kolom lengkap |
| POST ke endpoint diblokir (405 Method Not Allowed) | Tidak bisa kirim form search |

---

## 4. Strategi yang Dipilih: `verified_snapshot`

Berdasarkan temuan di atas, **satu-satunya jalur yang aman dan jujur** adalah:

1. **Dapatkan jadwal secara manual** — unduh dari BAAK langsung (website browser, file PDF yang diumumkan, atau via koordinator/akademik)
2. **Simpan sebagai snapshot JSON terverifikasi** di `services/baak-api/data/snapshots/`
3. **Deploy API yang membaca snapshot** — bukan scraping live
4. **Tandai data dengan metadata**: semester, tanggal verifikasi, sumber

### Format Snapshot JSON

```json
{
  "schema_version": "1.0",
  "semester": "PTA 2026/2027",
  "source_name": "BAAK Gunadarma",
  "source_url": "https://baak.gunadarma.ac.id/",
  "verified_at": "2026-10-24T09:00:00+07:00",
  "verified_by": "manual_download",
  "classes": {
    "3KA01": [
      {
        "hari": "Senin",
        "mata_kuliah": "Nama Mata Kuliah",
        "waktu": "1/2",
        "ruang": "D341",
        "dosen": "Nama Dosen"
      }
    ]
  }
}
```

---

## 5. Rekomendasi Langkah Selanjutnya

1. **Dapatkan file jadwal resmi** dari BAAK (PDF yang diumumkan atau via website di browser)
2. **Konversi ke JSON snapshot** sesuai format di atas
3. **Letakkan di** `services/baak-api/data/snapshots/PTA_2026_2027.json`
4. **Lanjut ke Fase 1** — implementasi Go API yang membaca snapshot + konversi 14 slot jam

### Hal yang TIDAK dilakukan (sesuai PRD)

- ❌ Bypass proteksi SSL/403 di produksi
- ❌ Mengandalkan `devel.baak.gunadarma.ac.id` sebagai sumber live (unstable, staging)
- ❌ Mengarang data jadwal sebagai placeholder produksi
- ❌ Menggunakan data dari referensi pihak ketiga tanpa verifikasi lisensi

---

## 6. Referensi

- `https://devel.baak.gunadarma.ac.id/kuliahUjian/4` — sumber tabel 14 slot jam
- `https://devel.baak.gunadarma.ac.id/kuliahUjian/6` — penjelasan format jadwal
- PRD: `docs/PRD_Integrasi_BAAK_Telegram_Personal_AI.md` Fase 0, Section 10
