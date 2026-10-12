# Konversi dokumen

Converter memakai paket internal `docconv`, yang hanya bergantung pada standard
library Python. Tidak ada `pypdf`, `pdfplumber`, `reportlab`, `python-docx`,
`openpyxl`, atau `python-pptx` — jadi tidak ada build native, tidak ada wheel
platform-specific, dan tidak ada kebutuhan `pip` tambahan untuk konversi.

```sh
python -m pip install -r requirements.txt
```

## Yang murni opsional

Tiga biner eksternal. Tidak ada di `requirements.txt` karena tidak bisa
di-pip; semuanya dideteksi saat runtime dan menampilkan pesan yang jelas bila
belum ada.

| Biner | Dipakai untuk | Cara memasang |
| --- | --- | --- |
| LibreOffice (`soffice`) | Word/Excel/PPT → PDF dengan layout asli | `LIBREOFFICE_BIN` atau `soffice` di PATH |
| poppler (`pdftoppm`) | PDF → gambar dan PDF → PPT | Windows: zip Release dari `oschwartz10612/poppler-windows`; Termux: `pkg install poppler`; lalu `POPPLER_BIN` atau PATH |
| tesseract | OCR untuk halaman scan | `TESSERACT_BIN` atau `tesseract` di PATH |

`python check_environment.py` menampilkan status ketiganya.

Penting: **ekstraksi teks PDF tidak butuh poppler maupun tesseract.** Yang
butuh hanya `pdftoppm` adalah PDF → gambar/PPT, dan hanya `tesseract` adalah OCR
halaman scan.

| Jalur | Cara kerja |
| --- | --- |
| Word/Excel/PPT → PDF | LibreOffice headless; fallback teks berisi sendiri dengan pembungkusan baris dan paginasi |
| PDF → Word | Ekstraksi teks + tabel; tabel menjadi paragraf bertanda `a \| b \| c` |
| PDF → Excel | Tabel dari geometri halaman masuk ke kolom; tanpa tabel, tiap baris teks di kolom A; satu sheet per halaman |
| PDF → PPT | `pdftoppm` merender tiap halaman ke PNG, rasio aspek dipertahankan dan dipusatkan |
| PDF → gambar | `pdftoppm` PNG 200 DPI |
| Gambar → PDF | PNG disisipkan apa adanya; JPEG disisipkan lewat `/DCTDecode` tanpa dikode ulang |

## Keterbatasan yang perlu diketahui

Bagian ini bukan daftar deficiencies yang tersembunyi, melainkan batas yang
tidak bisa dihilangkan tanpa menulis ulang mesin rendering.

- **Ekstraksi teks PDF lebih sederhana daripada pypdf.** PDF yang memakai CJK,
  ligatur, atau font subset tanpa `/ToUnicode` akan menghasilkan teks kosong
  atau salah. Mayoritas PDF hasil scan/Word berbahasa Indonesia aman.
- **Font subset tanpa `/ToUnicode` tidak dapat dipetakan.** Font `Type0`
  (Identity-H) seperti itu menghasilkan teks kosong, bukan karakter pengganti.
- **PDF terenkripsi ditolak** dengan pesan yang jelas. Belum ada dukungan RC4
  maupun AES; hapus proteksi kata sandi lebih dulu.
- **Deteksi tabel turun kualitasnya** dibanding pdfplumber. Tabel ber-grid
  (ada garis) akurat; tabel tanpa garis dideteksi dari jarak antar kata yang
  berulang, jadi bisa salah pada dokumen dengan kolom tidak rapi. Hasil yang
  meragukan lebih baik dibuang daripada diekspor salah.
- **Fallback Office → PDF tidak mempertahankan gambar, grafik, atau format.**
  Formula Excel ditampilkan sebagai teks, bukan dihitung. Font fallback
  (Courier) hanya mendukung Latin-1, sehingga dokumen beraksara non-Latin
  sebaiknya dikonversi lewat LibreOffice.
- **Gambar ke PDF hanya menerima PNG 8-bit RGB/RGBA non-interlaced dan JPEG
  baseline.** PNG 16-bit atau interlaced ditolak dengan pesan yang jelas;
  simpan ulang sebagai JPEG.

## Struktur internal

| Modul | Tanggung jawab |
| --- | --- |
| `docconv/_obj.py` | Lexer dan model objek PDF |
| `docconv/_xref.py` | xref table, xref stream, object stream, plus brute-force recovery |
| `docconv/_filter.py` | FlateDecode, LZW, ASCII85, ASCIIHex, RunLength, PNG/TIFF predictor |
| `docconv/_page.py` | Page tree, atribut yang diwarisi, deteksi `/Encrypt` |
| `docconv/_content.py` | Content stream → glyph berposisi |
| `docconv/_font.py` | Encoding dasar, `/Differences`, `/ToUnicode`, tabel lebar |
| `docconv/textlayout.py` | Glyph → baris → paragraf, jarak kata dari geometri |
| `docconv/table.py` | Deteksi tabel dari garis ruling atau jarak berulang |
| `docconv/pdfwrite.py` | Penulis PDF (font base-14 Courier) |
| `docconv/word.py`, `excel.py`, `slides.py` | Pembaca/penulis OOXML |
| `docconv/imgcodec.py` | Dimensi/penulis PNG, penyisipan gambar ke PDF |
| `ocr.py` | Pembungkus CLI tesseract |

## Menguji

Pembaca dan penulis PDF bisa sama-sama salah tanpa terdeteksi, jadi
`tests/fixtures/` berisi PDF asli yang dibuat library pihak ketiga
(reportlab). `tests/test_docconv.py` memvalidasi pembacaan kita terhadap file
itu — pengujian tidak bisa salah dua arah sekaligus karena keduanya tidak
memakai kode yang sama.

```sh
venv\Scripts\python.exe -m pytest tests/test_docconv.py tests/test_converter.py
```

Untuk membangun ulang fixture (butuh library pihak ketiga, tidak dijalankan
otomatis):

```sh
venv\Scripts\python.exe tests\make_fixtures.py
```