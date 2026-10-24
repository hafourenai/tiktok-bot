# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Modul Jadwal Kuliah BAAK Gunadarma — Website & Integrasi Telegram Personal AI

| Atribut | Keterangan |
|---|---|
| Versi | 1.0 — Draft implementasi |
| Tanggal | 24 Oktober 2026 |
| Proyek induk | `telegram_personal_ai` |
| Nama modul (usulan) | `baak_schedule` |
| Sasaran pengguna | Kelompok kecil mahasiswa (website); hanya pemilik akun (Telegram) |
| Status | Perencanaan — belum mengklaim integrasi data BAAK berhasil |
| Bahasa antarmuka | Indonesia |
| Zona waktu | Asia/Jakarta (WIB, UTC+07:00) |

> **Instruksi integrasi:** Dokumen ini dirancang untuk ditempatkan di `docs/PRD_Integrasi_BAAK_Telegram_Personal_AI.md` dalam proyek yang sudah ada. Ini adalah fitur tambahan, **bukan** instruksi membuat ulang atau mengganti aplikasi Telegram AI. AI coding agent wajib mengaudit struktur repo aktual sebelum menentukan lokasi file dan melakukan perubahan.

---

## 1. Ringkasan Produk

Bangun sistem jadwal kuliah Universitas Gunadarma yang menyajikan informasi BAAK dalam format lebih mudah dipahami. Website dapat diakses tanpa login oleh anggota kelompok untuk mencari jadwal berdasarkan kode kelas, melihat semua mata kuliah, dan membaca **rentang jam sebenarnya** yang dikonversi dari notasi jam kuliah BAAK. Di sisi lain, pemilik proyek dapat memeriksa jadwal melalui akun Telegram miliknya yang saat ini menjalankan sistem `telegram_personal_ai`.

Satu backend REST API berbasis **Go** bertugas mengambil/menerima data sumber yang diperbolehkan, menormalisasi, memvalidasi, mengonversi waktu, menyimpan snapshot/cache seperlunya, dan melayani **website maupun Telegram**. Backend diupayakan dapat dideploy ke Vercel; kompatibilitas runtime dan akses BAAK harus dibuktikan melalui pengujian.

**Batasan mendasar:** BAAK merupakan sumber rujukan akademik resmi. Produk ini merupakan antarmuka pihak ketiga dan **tidak** boleh menampilkan data contoh, data usang, atau hasil dugaan AI seolah-olah sebagai jadwal resmi yang terkini.

## 2. Masalah dan Tujuan

### 2.1 Masalah

- Jadwal kuliah menampilkan kode **jam ke-1**, **jam ke-1/2**, **jam ke-1/2/3**, dan seterusnya. Pengguna harus mengetahui sendiri rentang waktunya.
- Pembacaan jadwal per kelas melalui sumber asli kurang praktis untuk penggunaan cepat, terutama pada ponsel.
- Jadwal belum terhubung dengan asisten Telegram pribadi, sehingga pemilik perlu membuka sumber secara manual.

### 2.2 Tujuan (MVP)

1. Mahasiswa dapat mencari jadwal suatu kelas di website tanpa membuat akun.
2. Hasil jadwal menampilkan tepat tujuh kolom inti: **Kelas | Hari | Mata Kuliah | Waktu | Jam | Ruang | Dosen**.
3. `Waktu` menyimpan notasi jam dari sumber, misalnya `1/2`; `Jam` menampilkan rentang aktual, misalnya `07.30–09.30 WIB`.
4. Pemilik proyek dapat menjalankan perintah Telegram khusus jadwal tanpa memengaruhi mekanisme auto-reply yang sudah ada.
5. Website dan integrasi Telegram memakai **kontrak data API yang sama**.
6. Jika sumber BAAK gagal diakses, sistem tidak mengarang informasi; sistem memakai snapshot terverifikasi yang jelas ditandai, atau menampilkan pesan kegagalan.

### 2.3 Indikator keberhasilan

- Seluruh **14 slot jam** resmi memiliki unit test dan lolos konversi, termasuk slot tunggal maupun rentang.
- Pencarian berdasarkan kode kelas bekerja dari UI ke API sampai hasil (dengan fixture pengujian, lalu data nyata jika sumber tervalidasi).
- Data pada website dan Telegram identik untuk kelas yang sama dan snapshot/semester yang sama.
- Website dapat dipakai dengan nyaman pada layar ponsel serta keyboard.
- Fitur auto-reply Telegram yang lama lulus pengujian regresi setelah integrasi.
- Setiap data yang ditampilkan memiliki identitas sumber dan status pembaruan, atau ditandai sebagai demo jika belum nyata.

## 3. Pengguna dan Hak Akses

| Aktor | Hak dan kebutuhan |
|---|---|
| Pengunjung website | Tanpa login; mencari kode kelas dan memfilter jadwal; membaca sumber/status data. |
| Pemilik Telegram | Satu-satunya pengguna fitur jadwal Telegram, awalnya melalui **Saved Messages / Pesan Tersimpan** di akun sendiri. |
| Pengelola proyek | Memperbarui pengaturan sumber atau snapshot melalui proses pengembangan/deploy. Tidak perlu dashboard admin pada MVP. |

**Tidak ada** pendaftaran, password, akun mahasiswa, NPM, atau pengumpulan data pribadi mahasiswa untuk MVP.

## 4. Ruang Lingkup

### 4.1 Termasuk MVP (P0)

- Audit sumber jadwal publik BAAK dan aturan akses otomatis.
- Integrasi sumber melalui adapter yang dapat diganti: pengambilan data publik **bila diizinkan dan teknisnya memungkinkan**, serta **impor snapshot terverifikasi** jika tidak.
- Parsing dan normalisasi jadwal per kelas.
- Konversi notasi jam menjadi waktu nyata sesuai ketentuan BAAK (14 jam).
- REST API Go dengan validasi input, kesalahan terstandarisasi, dan informasi kesegaran data.
- Website responsif, tanpa login, pencarian kelas dan penyaring hari/mata kuliah.
- Telegram owner-only: `/jadwal <KELAS>` dan penggunaan kelas default (jika dikonfigurasi).
- Dokumentasi setup lokal, konfigurasi environment, deploy, serta pengujian.

### 4.2 Tahap lanjutan (P1 — bukan syarat MVP)

- Pertanyaan bahasa alami lewat model lokal, misalnya “Jadwalku besok apa?” dengan tool deterministik yang memanggil API; tidak mengandalkan ingatan LLM.
- Halaman detail per hari, fitur salin/bagikan jadwal, dan preferensi kelas lokal di perangkat.
- Dukungan jadwal ujian, kalender akademik, dan notifikasi bila sumber resmi berubah.
- Pemantauan perubahan jadwal dengan snapshot permanen/penjadwalan berkala **setelah** ada sumber yang stabil dan diizinkan.

### 4.3 Tidak termasuk

- Login/registrasi, role mahasiswa, dashboard admin, profil NPM, nilai/IPK, KRS, data mahasiswa pribadi.
- Membuat bot Telegram publik atau memberi fitur jadwal kepada pengguna lain pada akun Telegram pribadi.
- Mengganti engine LLM, knowledge base, mekanisme consent `/aiaktif`, dan fitur handoff yang sudah ada.
- Menjadikan AI sumber kebenaran untuk jadwal atau menggunakan data palsu sebagai data produksi.
- Menembus CAPTCHA, Cloudflare, autentikasi, atau kontrol akses situs sebagai asumsi utama desain.

## 5. User Stories dan Alur Utama

**US-01 — Pengunjung web mencari jadwal.** Pengunjung membuka URL, memasukkan kode kelas (mis. `3KA01`), klik **Cari Jadwal** / Enter, melihat daftar jadwal yang diurutkan berdasarkan hari lalu jam mulai. Kelas contoh hanya ilustrasi; data harus berasal dari sumber terverifikasi.

**US-02 — Pengunjung memahami kode jam.** Pengunjung melihat `Waktu: 1/2` dan `Jam: 07.30–09.30 WIB` dalam baris yang sama. Bila notasi tidak dapat diterjemahkan dengan yakin, `Jam` menjadi **“Belum dapat ditentukan”**, bukan angka tebakan.

**US-03 — Pengunjung memfilter.** Dari hasil kelas yang sama, pengguna memfilter hari atau mencari sebagian nama mata kuliah tanpa kehilangan informasi dasar.

**US-04 — Pemilik mengecek lewat Telegram.** Pemilik mengirim `/jadwal 3KA01` dari **Pesan Tersimpan**; aplikasi Telegram lokal memanggil API lalu mengirim ringkasan terstruktur. Perintah dari pengguna lain tidak diproses sebagai perintah khusus.

**US-05 — Ketika sumber gagal.** Pengunjung menerima informasi bahwa jadwal belum tersedia, atau melihat snapshot terakhir dengan label jelas **“Data terakhir diperbarui …; mungkin sudah berubah”**. Tidak ada klaim “real-time” bila tidak benar.

## 6. Functional Requirements

| ID | Prioritas | Kebutuhan | Kriteria penerimaan singkat |
|---|---|---|---|
| FR-01 | P0 | Pencarian berdasarkan kode kelas | Input dinormalisasi (`trim`, uppercase), divalidasi, dan dikirim ke API. |
| FR-02 | P0 | Tujuh kolom wajib | Urutan tepat: Kelas, Hari, Mata Kuliah, Waktu, Jam, Ruang, Dosen. |
| FR-03 | P0 | Konversi rentang jam BAAK | `1` → `07.30–08.30`; `1/2` → `07.30–09.30`; `5/6` → `11.30–13.30`. |
| FR-04 | P0 | Preservasi notasi asli | Field `waktu` tetap berisi data/notasi dari sumber yang telah dinormalisasi, tidak diganti jam nyata. |
| FR-05 | P0 | Metadata jadwal | Respons menyertakan asal data, waktu pengambilan, semester bila ada, dan indikator stale. |
| FR-06 | P0 | Penyaring hari | Filter case-insensitive terhadap daftar jadwal kelas. |
| FR-07 | P0 | Pencarian mata kuliah | Pencocokan sebagian nama dari jadwal kelas yang telah diperoleh. |
| FR-08 | P0 | Urut kronologis | Hari Senin–Minggu, kemudian `jam_mulai`; entri tanpa jam valid di belakang pada hari yang sama. |
| FR-09 | P0 | Data tidak lengkap | Ruang/dosen yang tidak tersedia ditampilkan **“Belum tersedia”**; tidak diisi nama fiktif. |
| FR-10 | P0 | Kondisi UI | Loading, input invalid, hasil kosong, sumber tidak tersedia, cached/stale, dan berhasil tertangani. |
| FR-11 | P0 | Integrasi owner Telegram | `/jadwal <KELAS>` hanya pada Saved Messages, identitas diverifikasi menggunakan ID akun sendiri. |
| FR-12 | P0 | Isolasi Telegram | Auto-reply, `/aiaktif`, penundaan, handoff manual, RAG, dan LLM lama tetap berjalan sebagaimana semula. |
| FR-13 | P0 | Adapter sumber | `OfficialPublicSource` (jika disetujui/tersedia) dan `VerifiedSnapshotSource`; keduanya menghasilkan model yang sama. |
| FR-14 | P0 | Kesalahan API konsisten | Kode error terstruktur; jangan kirim HTML sumber atau stack trace ke klien. |
| FR-15 | P0 | Cache/penyimpanan | Request UI berulang tidak memicu fetch ke BAAK tanpa kendali; snapshot memiliki tanggal dan semester. |
| FR-16 | P0 | Tautan ke sumber | UI menampilkan atribusi “Sumber: BAAK Gunadarma” serta link sumber bila diketahui. |
| FR-17 | P1 | Pertanyaan natural Telegram | Ekstraksi kelas/hari menggunakan parsing deterministik; LLM lokal hanya untuk memahami/merangkum, bukan membuat isi jadwal. |

## 7. Aturan Bisnis: Konversi Jam

BAAK membagi satu hari ke **14 jam kuliah**, masing-masing satu jam. Tabel rujukan:

| Jam ke- | Mulai | Selesai |
|---:|:---:|:---:|
| 1 | 07.30 | 08.30 |
| 2 | 08.30 | 09.30 |
| 3 | 09.30 | 10.30 |
| 4 | 10.30 | 11.30 |
| 5 | 11.30 | 12.30 |
| 6 | 12.30 | 13.30 |
| 7 | 13.30 | 14.30 |
| 8 | 14.30 | 15.30 |
| 9 | 15.30 | 16.30 |
| 10 | 16.30 | 17.30 |
| 11 | 17.30 | 18.30 |
| 12 | 18.30 | 19.30 |
| 13 | 19.30 | 20.30 |
| 14 | 20.30 | 21.30 |

**Aturan kalkulasi**:

1. `Waktu` menyimpan notasi slot yang tertera, contoh `1`, `1/2`, `1/2/3`, `4/5`.
2. Parser menerima token slot 1–14 yang berupa deret berurutan, termasuk format yang benar-benar ditemukan pada sumber. Jangan menafsirkan notasi lain tanpa verifikasi/tes.
3. `jam_mulai` = awal slot terkecil; `jam_selesai` = akhir slot terbesar; `Jam` adalah gabungan keduanya dengan format `HH.mm–HH.mm WIB`.
4. `1` = `07.30–08.30 WIB`, sedangkan `1/2` = `07.30–09.30 WIB`; **keduanya berbeda**.
5. Kode di luar 1–14, kosong, duplikat, tidak berurutan, atau tidak dikenal → `jam = null`, dan tambahkan `warnings`; jangan mengarang.
6. Konversi murni berdasarkan tabel resmi, **bukan inferensi AI**. Pertahankan `waktu` asli untuk audit.
7. Jika sumber memuat informasi jam nyata yang bertentangan, tandai konflik untuk verifikasi manual, jangan diam-diam menimpa.

Sumber resmi aturan waktu: https://baak.gunadarma.ac.id/kuliahUjian/5 (subhalaman Jadwal Kuliah; URL dapat berubah). Salinan deskripsi juga terlihat pada https://devel.baak.gunadarma.ac.id/kuliahUjian/4.

## 8. Desain UX Website

### 8.1 Halaman utama

- Judul sederhana: **Jadwal Kuliah Gunadarma** dan catatan bahwa ini website komunitas/tidak resmi.
- Form pencarian kelas dengan tombol **Cari Jadwal**; pencarian bisa dipicu Enter.
- Tampilan hasil utama: **tabel desktop** dengan tujuh kolom sesuai persyaratan; **kartu per mata kuliah** di mobile bila tabel terlalu sempit, tetapi seluruh informasi tetap tersedia.
- Filter hari (`Semua Hari`, Senin, Selasa, dst.) dan input filter nama mata kuliah.
- Hasil diurutkan, dengan penekanan visual pada **Jam** yang sudah dikonversi.
- Footer/status: **Sumber**, **Semester** (jika valid), **Diambil/Diperbarui pada**, **Status data** (terbaru/tersimpan/usang), link ke BAAK.
- Aksesibel: label input, kontras, navigasi keyboard, target sentuh yang nyaman, indikator loading.

### 8.2 Empty/error states

| Kondisi | Pesan contoh |
|---|---|
| Belum cari | “Masukkan kode kelas untuk melihat jadwal.” |
| Kode tidak valid | “Format kode kelas belum valid.” |
| Kelas tidak ditemukan | “Jadwal untuk kelas ini tidak ditemukan pada sumber yang tersedia.” |
| Data sumber belum terhubung | “Jadwal belum tersedia. Periksa kembali di BAAK.” |
| Snapshot usang | “Menampilkan data tersimpan; jadwal mungkin telah berubah.” |
| Waktu gagal dikonversi | “Belum dapat ditentukan (kode: …).” |

Tidak boleh menggunakan dataset ilustrasi pada mode produksi tanpa tanda **DEMO** yang sangat jelas.

## 9. API Contract (Rancangan)

**Base URL:** `https://<domain-api>/api/v1` (nama domain akan ditentukan saat deploy).

### 9.1 Endpoint

| Method & Path | Deskripsi |
|---|---|
| `GET /jadwal?kelas=3KA01` | Jadwal untuk satu kelas. `kelas` wajib. |
| `GET /jadwal?kelas=3KA01&hari=Senin` | Jadwal kelas tersaring hari. |
| `GET /jadwal?kelas=3KA01&mata_kuliah=basis` | Jadwal kelas tersaring nama mata kuliah. |
| `GET /jam-kuliah` | Daftar 14 slot dan waktu baku (berguna untuk UI/tes). |
| `GET /health` | Status API dan ketersediaan sumber dalam format aman. |

**Semantik respons:** jika kelas tidak ada pada dataset lengkap dan valid → 404; jika kelas ada tetapi filter tidak punya hasil → 200 dengan `data: []`. Jangan menyimpulkan kelas tidak ada ketika sumber justru sedang gagal.

### 9.2 Model hasil

```json
{
  "success": true,
  "kelas": "3KA01",
  "semester": "PTA 2026/2027",
  "data": [
    {
      "kelas": "3KA01",
      "hari": "Senin",
      "mata_kuliah": "CONTOH MATA KULIAH",
      "waktu": "1/2",
      "jam": "07.30–09.30 WIB",
      "jam_mulai": "07:30",
      "jam_selesai": "09:30",
      "ruang": "CONTOH RUANG",
      "dosen": null,
      "warnings": []
    }
  ],
  "meta": {
    "source_name": "BAAK Gunadarma",
    "source_url": "https://baak.gunadarma.ac.id/",
    "source_mode": "verified_snapshot",
    "fetched_at": "2026-10-24T09:00:00+07:00",
    "is_stale": false,
    "status": "ok"
  }
}
```

> Seluruh nilai kelas, mata kuliah, ruang, tanggal, dan semester pada contoh JSON adalah **ilustrasi kontrak**, bukan klaim jadwal nyata. `source_mode` yang disepakati: `official_public` atau `verified_snapshot`. `fetched_at` harus benar-benar berasal dari proses pengambilan/verifikasi yang terjadi; jangan hardcode tanggal contoh.

### 9.3 Error terstandarisasi

```json
{
  "success": false,
  "error": {
    "code": "SOURCE_UNAVAILABLE",
    "message": "Sumber jadwal belum dapat diakses dan tidak ada snapshot terverifikasi."
  }
}
```

Kode minimal: `VALIDATION_ERROR` (400), `CLASS_NOT_FOUND` (404), `RATE_LIMITED` (429), `SOURCE_UNAVAILABLE` (503), `INTERNAL_ERROR` (500). `is_stale` hanya `false` bila data lolos kebijakan freshness saat diminta.

## 10. Sumber Data, Cache, dan Ketahanan

**Gate sebelum mengambil data nyata**:

1. Inspeksi halaman jadwal resmi BAAK, kolom yang benar-benar tersedia, pola URL/request, dan izin/ketentuan akses yang relevan.
2. Uji akses dari lingkungan lokal **dan** lingkungan deployment. Hasil yang sukses di browser bukan jaminan sukses pada Vercel.
3. Jangan merancang ketergantungan pada bypass proteksi situs. Bila endpoint publik tidak dapat diambil dengan cara yang diizinkan, gunakan **impor terverifikasi** dari jadwal yang didapat secara sah, atau minta akses/sumber resmi.
4. Catat status penelitian sumber dalam `docs/baak-source-validation.md`: URL, contoh HTML (tanpa data sensitif), bidang yang tersedia, tanggal tes, hasil, dan kendala.

**Kebijakan cache**:

- Hindari fetch BAAK untuk setiap request website/Telegram; cache berdasarkan kelas dan semester.
- Nilai awal TTL yang dapat dikonfigurasi: 6 jam, hanya setelah kebijakan sumber diverifikasi. Jangan mengklaim selalu terbaru.
- **Serverless cache in-memory tidak persisten antar instance/deploy**. Untuk fallback yang andal gunakan file snapshot JSON versioned (di dalam repo/build) pada MVP, atau penyimpanan eksternal persisten bila nanti dibutuhkan.
- Snapshot memuat `schema_version`, semester, kelas, sumber, waktu verifikasi, dan array jadwal. Verifikasi format dengan schema/tes sebelum deploy.
- Saat live fetch gagal, snapshot valid bisa ditampilkan dengan `is_stale: true` sesuai aturan. Snapshot dari semester lama **tidak** boleh otomatis diklaim sebagai jadwal semester berjalan.
- Jika data source mengalami perubahan struktur, hentikan parsing berisiko dan tampilkan error/fallback dengan jelas.

**Status ketersediaan:** implementasi `ok`, `stale`, `unavailable` secara konsisten. Ketersediaan data nyata bergantung pada izin dan hasil validasi sumber, sehingga tidak menjadi janji otomatis MVP.

## 11. Integrasi dengan `telegram_personal_ai`

### 11.1 Komponen yang harus dipertahankan

- **Telethon** sebagai klien Telegram personal (bukan migrasi ke Bot API pada MVP).
- Auto-reply pribadi berbasis consent per chat: perintah `/aiaktif` dan aturan opt-in yang sudah ada.
- Mekanisme jeda balasan dan **human/manual takeover**; hindari race condition yang membuat AI membalas setelah pemilik mengambil alih.
- Knowledge base RAG `knowledge/`, indeks **SQLite FTS5**, dan konfigurasi prompt di `app/llm.py`.
- Model lokal yang sudah dikembangkan, misalnya **Qwen3 0.6B** melalui **llama.cpp** di endpoint OpenAI-compatible; jangan mengganti provider/model agar fitur jadwal bekerja.
- Seluruh `.env`, file sesi Telethon, dan secret lokal tetap tidak dikirim ke frontend atau repo publik.

### 11.2 Alur baru P0

1. Pemilik membuka **Pesan Tersimpan (Saved Messages)**.
2. Pemilik mengirim `/jadwal 3KA01`.
3. Handler lokal memverifikasi bahwa event berada dalam chat diri sendiri, identitas adalah akun pemilik, dan perintah sesuai pola (bukan DM/grup pihak lain).
4. Handler memanggil `GET /api/v1/jadwal?kelas=3KA01` dengan timeout yang dapat dikonfigurasi.
5. Handler memformat hasil (hari, mata kuliah, Waktu, Jam, ruang, dosen; status data), lalu mengirim respons ke Pesan Tersimpan.
6. Perintah dicegat **sebelum** alur auto-reply umum dan tidak menciptakan activation state `/aiaktif`.

Pemilik dapat mengatur kelas default lewat `BAAK_DEFAULT_CLASS`, sehingga `/jadwal` tanpa parameter menggunakan kelas default bila tersedia; jika tidak, kirim panduan singkat.

### 11.3 Alur P1: pertanyaan alami

- Input: “Jadwal kelas 3KA01 hari Selasa?” atau “Besok ada kuliah apa?”
- Resolusi hari menggunakan **Asia/Jakarta**; “besok” dihitung dari tanggal lokal aktual, bukan asumsi model.
- Parser/route deterministik mengidentifikasi kelas/hari, lalu memanggil API. LLM lokal boleh merapikan bahasa hasil tetapi **tidak boleh mengganti isi** record API.
- Bila identitas kelas tidak ada, gunakan default yang disetel pemilik; jika belum disetel, minta kode kelas.
- Jangan mengirim pertanyaan jadwal dari pihak lain di DM kepada fitur owner-only.

### 11.4 Penanganan kegagalan

Ketika timeout/offline/HTTP error, balas dengan informasi kegagalan yang jelas. Jangan menanyakan LLM untuk menebak jadwal. Kegagalan API tidak boleh menghentikan listener Telegram, auto-reply, atau layanan LLM lokal.

## 12. Arsitektur & Struktur Folder Usulan

```text
telegram_personal_ai/                 # proyek asli; jangan dirombak tanpa audit
├── main.py                           # entry point eksisting (perubahan minimal)
├── app/                              # modul auto-reply/RAG/LLM eksisting
│   ├── llm.py                        # jangan ganti kontrak LLM
│   ├── baak_client.py                # BARU: HTTP client API jadwal
│   └── schedule_commands.py          # BARU: owner-only Telegram handler
├── knowledge/                        # tetap
├── scripts/                          # tetap
├── services/
│   └── baak-api/                     # BARU: Go REST API (deployable terpisah)
│       ├── go.mod
│       ├── main.go                   # atau entrypoint Go Vercel yang kompatibel
│       ├── internal/
│       │   ├── source/               # adapter official / verified snapshot
│       │   ├── parser/               # ekstraksi & normalisasi
│       │   ├── schedule/             # konversi jam & validasi
│       │   └── httpapi/              # handler, middleware
│       ├── data/snapshots/            # snapshot terverifikasi, bila digunakan
│       └── tests/                    # test fixtures dan unit/integration tests
├── web/
│   └── baak-schedule/                # BARU: frontend terpisah
│       ├── src/
│       ├── public/
│       └── package.json
├── docs/
│   ├── PRD_Integrasi_BAAK_Telegram_Personal_AI.md
│   ├── baak-api-contract.md
│   └── baak-source-validation.md
└── .env.example                      # hanya contoh variabel; jangan isi secret
```

**Catatan:** lokasi di atas adalah **usulan**, bukan klaim struktur repo saat ini. Jika nama file/folder berbeda, adaptasikan secara minimal. Proyek Go dan frontend web boleh berada dalam satu repo tetapi **menjadi dua root/deployment Vercel** untuk memudahkan konfigurasi, sementara Telethon tetap dijalankan pada perangkat/lingkungan Telegram yang ada. Hindari asumsi Go API dapat berjalan terus-menerus sebagai server lokal di HP.

**Diagram alur**:

```text
Sumber publik BAAK yang diizinkan / snapshot terverifikasi
                          ↓
          Go REST API + normalizer + converter
                          ↓
                JSON + metadata sumber
                     ↙             ↘
              Website publik      Telegram owner-only
              (tanpa login)      (Telethon/Python lokal)
```

## 13. Rekomendasi Teknologi & Deployment

| Lapisan | Rekomendasi | Alasan |
|---|---|---|
| Backend API | Go (`net/http` atau router ringan) | Sesuai rancangan, sederhana, kuat untuk parsing dan JSON. |
| Hosting API | Vercel Go runtime (uji lebih dulu) | Dukungan resmi Go tersedia, **masih Beta** per dokumentasi yang diperiksa. |
| Website | React + Vite atau stack frontend yang sudah tersedia | Mobile-first; tidak memerlukan SSR untuk MVP; jangan menambah stack besar tanpa kebutuhan. |
| Hosting website | Vercel/static hosting | Mudah berbagi link kepada kelompok. |
| Telegram | Python + Telethon (eksisting) | Tidak memigrasi arsitektur bot yang sudah berjalan. |
| LLM | Tetap menggunakan model lokal eksisting | Fitur `/jadwal` P0 tidak bergantung pada AI. |
| Data | JSON snapshot terverifikasi + cache | Tanpa database baru pada MVP bila kebutuhan masih kecil. |

**Deployment:** tentukan root direktori untuk Go dan web, dokumentasikan env, konfigurasi CORS web resmi, dan uji request dari ponsel, laptop, serta runtime Telegram. Vercel Go runtime mengikuti konfigurasi/preset terbaru yang didukung; jangan memakai konfigurasi lama tanpa dites. Tidak ada jaminan nol biaya di luar kuota/ketentuan platform.

### 13.1 Environment yang diusulkan

**Service Go** (nonsecret kecuali nanti ada kredensial sumber resmi):

- `BAAK_SOURCE_MODE=verified_snapshot|official_public`
- `BAAK_SOURCE_BASE_URL=https://baak.gunadarma.ac.id`
- `BAAK_HTTP_TIMEOUT_SECONDS=10`
- `BAAK_CACHE_TTL_SECONDS=21600`
- `BAAK_ALLOWED_ORIGINS=https://<domain-website>`

**Telegram Python (tambahan saja, tidak mengganti env lama):**

- `BAAK_API_BASE_URL=https://<domain-api>/api/v1`
- `BAAK_DEFAULT_CLASS=` (opsional)
- `BAAK_REQUEST_TIMEOUT_SECONDS=10`

**Frontend:**

- `VITE_BAAK_API_BASE_URL=https://<domain-api>/api/v1`

Tidak ada API key rahasia yang disimpan dalam browser. Pembatasan CORS bukan pengganti rate limiting karena REST API tetap publik.

## 14. Non-Functional Requirements

### 14.1 Keamanan dan privasi

- Website read-only tanpa autentikasi; hanya akses data publik yang sesuai izin.
- Batasi kode kelas ke karakter/panjang wajar, lakukan escaping output, batasi ukuran payload, dan cegah injeksi query/path.
- Terapkan rate limiting di gateway/platform (atau mekanisme persisten lintas instance); **in-memory rate limiter tidak menjamin batas global di serverless**.
- Batasi origin CORS untuk browser, namun anggap API dapat diakses oleh klien nonbrowser.
- Telegram owner-only divalidasi dengan ID akun dan konteks Saved Messages, bukan sekadar username/perintah teks.
- Jangan log isi sesi Telethon, `.env`, prompt pribadi, atau kredensial; jangan commit file `.session`, `.env`, cache rahasia.
- Untuk penggunaan pustaka/komponen dari proyek pihak ketiga, evaluasi lisensi (contoh referensi `yafyx/baak-api` berlisensi GPL-3.0) sebelum menyalin kode.

### 14.2 Keandalan

- Timeout terpisah antara fetch sumber dan respons Telegram; jangan biarkan panggilan tak berujung.
- Pembedaan eksplisit error “kelas tidak ditemukan”, “format input salah”, dan “sumber tidak tersedia”.
- Cache/snapshot yang digunakan diberi metadata untuk mencegah salah informasi semester.
- Parser memiliki fixture HTML/JSON lokal agar CI tidak bergantung pada BAAK setiap kali berjalan.

### 14.3 Performa dan kompatibilitas

- Sasaran awal: hasil cached/verified snapshot API respons < 1 detik pada pengujian lokal yang wajar; hasil cold start / internet dapat lebih lambat dan dicatat, bukan dijanjikan mutlak.
- Website responsif pada lebar ponsel sekitar 360 px hingga desktop.
- Aksesibilitas keyboard dan teks status memadai; animasi bukan prioritas.

## 15. Rencana Pengujian

| ID | Pengujian | Harapan |
|---|---|---|
| TC-01 | `waktu=1` | `jam=07.30–08.30 WIB` |
| TC-02 | `waktu=1/2` | `jam=07.30–09.30 WIB` |
| TC-03 | `waktu=1/2/3` | `jam=07.30–10.30 WIB` |
| TC-04 | `waktu=4/5` | `jam=10.30–12.30 WIB` |
| TC-05 | `waktu=5/6` | `jam=11.30–13.30 WIB` |
| TC-06 | `waktu=14` | `jam=20.30–21.30 WIB` |
| TC-07 | Semua 14 slot satuan | Semua hasil sesuai tabel resmi |
| TC-08 | `waktu=2/4`, `15`, string kosong | Tidak dikonversi; warning, bukan tebakan |
| TC-09 | Kode kelas huruf kecil + spasi | Dinormalisasi dan hasil sama |
| TC-10 | Filter hari dan mata kuliah | Hasil benar dan urut kronologis |
| TC-11 | `dosen=null` / `ruang=null` | UI menampilkan “Belum tersedia” |
| TC-12 | Sumber offline, snapshot valid | Tampilkan data tersimpan dengan status stale yang tepat |
| TC-13 | Sumber offline, snapshot tidak ada | 503 dan pesan ramah, tidak ada jadwal palsu |
| TC-14 | Snapshot semester berbeda | Jangan mengklaim sebagai semester saat ini |
| TC-15 | Perintah `/jadwal` dari Saved Messages | Hanya owner mendapatkan respons |
| TC-16 | Perintah dari orang lain / chat grup | Tidak diproses oleh handler jadwal |
| TC-17 | Perintah `/aiaktif` dan handoff lama | Tidak berubah (regresi) |
| TC-18 | Buka web di mobile / desktop | Semua tujuh field terbaca dan navigasi baik |
| TC-19 | Sumber HTML berubah | Parser fail safe, tidak menghasilkan data salah diam-diam |

Gunakan fixture sintetik hanya untuk tes/demo; **dilarang** memperlakukannya sebagai jadwal produksi.

## 16. Rencana Tahapan Implementasi

### Fase 0 — Audit dan verifikasi sumber (wajib)

1. Audit repo `telegram_personal_ai` (termasuk handlers, konfigurasi, tests, dependensi, dan startup).
2. Validasi struktur/sumber data BAAK dan ketentuan akses; dokumentasikan temuan secara nyata.
3. Tetapkan strategi `official_public` yang benar-benar bekerja **atau** `verified_snapshot` sebagai jalur awal.
4. Finalisasi bentuk dataset dan contract API dari sampel yang benar-benar telah diverifikasi.

**Gate:** Jangan menyebut integrasi “live BAAK” berhasil sebelum request dari environment target benar-benar teruji.

### Fase 1 — Go API + aturan waktu

1. Implementasi model, parser/adapters, konversi slot, validasi, dan endpoint.
2. Implementasi metadata kesegaran data, cache/fallback, unit test dan fixture.
3. Uji lokal, lalu deployment percobaan; periksa cold-start, CORS, dan ketersediaan sumber.

### Fase 2 — Website

1. Implementasi form kelas, tabel desktop / kartu mobile, filter hari dan mata kuliah.
2. Implementasi loading/empty/error/stale states dan footer sumber.
3. Uji kompatibilitas responsive dan integrasi API yang dideploy.

### Fase 3 — Telegram

1. Tambahkan client HTTP Python ke API yang sama.
2. Tambahkan handler owner-only `/jadwal` di Saved Messages tanpa mengubah flow umum.
3. Jalankan tes regresi auto-reply, `/aiaktif`, handoff, dan kegagalan jaringan.
4. P1 (opsional setelah P0 stabil): routing pertanyaan jadwal melalui LLM lokal.

### Fase 4 — Rilis & dokumentasi

1. Lengkapi README langkah setup, env, cara impor snapshot, URL deploy dan troubleshooting.
2. Lakukan smoke test dengan kelas sungguhan yang izin/sumber datanya tervalidasi.
3. Catat keterbatasan: tidak resmi, status data, dan ketergantungan pada BAAK.

## 17. Definition of Done (MVP)

MVP **selesai** apabila seluruh poin berikut terpenuhi:

- [ ] Repo Telegram eksisting tetap dapat dijalankan tanpa modul BAAK ketika fiturnya dinonaktifkan.
- [ ] Seluruh test konversi 14 slot dan rentang contoh lulus.
- [ ] Go API memiliki dokumentasi contract, status sumber, error handling, dan tes.
- [ ] Website tanpa login menampilkan tujuh field dengan benar dan responsif.
- [ ] `Waktu` dan `Jam` jelas berbeda; tidak ada jadwal yang diciptakan AI.
- [ ] Sumber jadwal terverifikasi dan statusnya jujur; apabila belum tersedia, UI menyatakan keterbatasannya.
- [ ] Telegram Saved Messages owner-only bekerja; perintah pihak lain tidak memicu fungsi ini.
- [ ] `/aiaktif`, RAG, human takeover, dan auto-reply lama lulus regression tests.
- [ ] Semua secret tetap aman; dokumentasi `.env.example` tersedia.
- [ ] Penerapan nyata (web + API + Telegram) diuji ujung-ke-ujung, atau blocker dicatat eksplisit tanpa klaim “selesai”.

## 18. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| BAAK memblokir scraping / mengubah HTML | Jadwal tidak tersedia atau keliru | Gate sumber, adapter terpisah, snapshot terverifikasi, pesan kesalahan jelas. |
| Serverless cache tidak persisten | Fetch berulang; fallback hilang | Snapshot JSON versioned atau storage persisten sebelum mengklaim cache andal. |
| Jadwal semester lama terbaca sebagai baru | Salah jadwal kuliah | Validasi semester + metadata, label stale, jangan auto-anggap terbaru. |
| Parse kode jam tidak dikenal | Waktu salah | Strict parser; tampilkan unknown + warning. |
| Handler Telegram bentrok auto-reply | Respons ganda / privasi terganggu | Owner-only Saved Messages, prioritas dispatch, regresi. |
| Go runtime/deploy belum sesuai | API gagal di Vercel | Uji runtime dan fungsi sejak fase 1; dokumentasi adaptasi. |
| Kode pihak ketiga berlisensi | Risiko kepatuhan lisensi | Referensi konsep boleh; evaluasi lisensi sebelum salin kode. |
| API publik disalahgunakan | Beban/batas layanan | Rate limit platform, caching, input limits, observabilitas ringan. |

## 19. Instruksi Eksekusi untuk AI Coding Agent

> **Penting:** Kerjakan fitur ini sebagai ekspansi repo `telegram_personal_ai`, bukan project baru yang menggantikan repo induk.
>
> 1. **Mulai dari membaca repo yang sebenarnya:** laporkan struktur dan entrypoint, dependency, handler Telethon, `.env.example`, pengujian yang ada, dan titik integrasi yang paling aman.
> 2. **Jangan menghapus, memindahkan, atau memodifikasi fitur eksisting secara tidak perlu.** Pertahankan `/aiaktif`, model lokal, prompt, RAG SQLite FTS5, dan human takeover.
> 3. **Implementasikan bertahap:** Fase 0 → API Go + konversi → web → Telegram. Jangan mengaku sudah mengintegrasikan live BAAK sebelum terbukti.
> 4. **Sumber harus kredibel:** jika akses BAAK publik tidak bisa digunakan secara sah/stabil, berhenti pada adapter snapshot terverifikasi serta dokumentasikan blocker. Jangan menembus proteksi situs atau memasukkan data palsu sebagai live.
> 5. **Satu kontrak JSON untuk dua klien:** website dan Telegram harus memakai response API yang sama.
> 6. **Pisahkan batas deployment:** Go API dan website bisa dideploy terpisah dari satu monorepo; Python/Telethon berjalan seperti sebelumnya.
> 7. **Uji dan laporkan:** sertakan daftar file berubah, hasil test, cara menjalankan lokal, env tambahan, URL jika memang telah dideploy, dan hal yang belum berfungsi.
> 8. **Jangan menyalin kode dari referensi GPL tanpa meninjau implikasi lisensinya.**

## 20. Referensi

1. [BAAK Gunadarma — situs resmi](https://baak.gunadarma.ac.id/)
2. [BAAK — penjelasan jadwal kuliah dan 14 slot jam](https://baak.gunadarma.ac.id/kuliahUjian/5)
3. [BAAK — halaman penjelasan alternatif/development](https://devel.baak.gunadarma.ac.id/kuliahUjian/4)
4. [Vercel — Using the Go Runtime with Vercel Functions](https://vercel.com/docs/functions/runtimes/go)
5. [Proyek referensi pihak ketiga: yafyx/baak-api](https://github.com/yafyx/baak-api) — referensi arsitektur; status, akses, dan lisensi harus dinilai mandiri.

---

**Catatan akhir:** dokumen ini menggambarkan persyaratan dan desain target, **bukan klaim API, website, atau integrasi Telegram sudah dibuat dan berjalan**. Sumber jadwal yang valid adalah syarat utama sebelum menayangkan data produksi.
