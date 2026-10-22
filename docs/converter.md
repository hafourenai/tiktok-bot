# Konversi dokumen

Converter mendukung konversi multi-format antar dokumen dengan dua tier kualitas:

1. **Tier 1 (Optimal):** LibreOffice headless untuk Office → PDF, pdfplumber + python-docx/openpyxl/python-pptx untuk formatted backends
2. **Tier 2 (Enhanced fallback):** reportlab untuk Office → PDF dengan tabel & heading
3. **Tier 3 (Basic fallback):** paket internal `docconv` dengan standard library Python saja

Sistem cascade otomatis: jika tier superior gagal atau tidak tersedia, lanjut ke tier berikutnya.

## Format yang didukung

| Konversi | Tier 1 | Tier 2 | Tier 3 | Fitur |
|----------|--------|--------|--------|-------|
| **PDF → DOCX** | - | ✅ | ✅ | Font, bold, tabel, images, heading hierarchy |
| **PDF → XLSX** | - | ✅ | ✅ | Header styling, column width, borders, cell colors |
| **PDF → PPTX** | - | ✅ | ✅ | Editable text boxes, tables, images |
| **PDF → Images** | - | - | ✅ | PNG 200 DPI (needs poppler) |
| **Image → PDF** | - | - | ✅ | PNG/JPEG lossless |
| **Office → PDF** | ✅ | ✅ | ✅ | LibreOffice best; enhanced fallback dengan tabel |
| **PDF → PDF terkompresi** | Ghostscript | - | - | Pilihan ringan/sedang/tinggi; hanya dikirim bila lebih kecil |

## Instalasi dependencies

### Requirements default (di requirements.txt)

```sh
python -m pip install -r requirements.txt
```

Ini mencakup:
- `python-telegram-bot` untuk bot Telegram
- Library standar `docconv` untuk converter dasar

### Optional: Enhanced formatting backends

Untuk quality tier 2 (formatted backends dengan pdfplumber, python-docx, openpyxl, python-pptx):

```sh
python -m pip install -e ".[formatted]"
```

Atau manual:

```sh
python -m pip install pdfplumber>=0.11,<1 python-docx>=1.1,<2 openpyxl>=3.1,<4 python-pptx>=0.6,<1 reportlab>=4.0,<5
```

### Optional: External binaries

Tidak ada di pip; deteksi runtime dan tampilkan pesan jika belum ada.

| Biner | Dipakai untuk | Instalasi |
|-------|-------|-----------|
| LibreOffice (`soffice`) | Office → PDF tier 1 (best quality) | `LIBREOFFICE_BIN` env var atau `soffice` di PATH |
| poppler (`pdftoppm`) | PDF → gambar, PDF → PPT rendering | Windows: zip dari `oschwartz10612/poppler-windows`; Termux: `pkg install poppler` |
| tesseract | OCR halaman scan | `TESSERACT_BIN` env var atau `tesseract` di PATH |
| Ghostscript (`gs`) | Kompres PDF | Termux: `pkg install ghostscript`; opsi `GHOSTSCRIPT_BIN` |

Kirim PDF ke bot dan pilih tombol kompresi. Pemrosesan lokal dibatasi 3 menit; file sementara dihapus setelah pengiriman. PDF yang sudah optimal tidak dikirim ulang. Kompresi tingkat tinggi dapat menurunkan kualitas gambar; periksa hasil sebelum dipakai.

Check status: `python check_environment.py`

**Penting:** PDF text extraction tidak butuh poppler/tesseract. Hanya PDF → images/PPT yang butuh poppler; hanya OCR scan pages yang butuh tesseract.

## Detail setiap konversi

### PDF → DOCX (Enhanced formatting)

**Tier 2 fitur:**
- ✅ Font preservation: Times New Roman, Arial, size 10-14pt
- ✅ Bold/italic detection dari PDF fontname
- ✅ Heading hierarchy (Heading 1, Heading 2)
- ✅ Editable tables dengan preserved structure
- ✅ Image embedding (JPEG signatures, logos)
- ✅ Paragraph spacing & line spacing 1.15
- ✅ Center-aligned titles, left-aligned body

**Fallback (Tier 3):**
- Text ekstraksi + tabel sebagai `cell | cell | cell`
- Heading detection dari text pattern
- Gambar tidak disertakan

### PDF → XLSX (Enhanced formatting)

**Tier 2 fitur:**
- ✅ Header row styling: bold font + light gray background
- ✅ Auto-detect column widths dari content
- ✅ Cell borders & table structure
- ✅ Preserve cell background colors dari PDF
- ✅ One sheet per page
- ✅ Proper cell alignment & wrapping

**Fallback (Tier 3):**
- Table → kolom CSV style
- Text sebagai rows di kolom A
- Satu sheet per halaman

### PDF → PPTX (Editable content)

**Tier 2 fitur:**
- ✅ Extract text ke editable text boxes (bukan rasterization)
- ✅ Embed tables sebagai PowerPoint objects (editable)
- ✅ Extract images & position correctly
- ✅ Heading detection & formatting
- ✅ Smart layout per slide
- ✅ Page title otomatis

**Fallback (Tier 1 via poppler):**
- Render halaman → PNG
- Embed sebagai slide image (no text editing)
- Maintains aspect ratio

### PDF → Images

**Requirements:**
- poppler (`pdftoppm`) untuk rendering

**Output:**
- PNG 200 DPI per halaman
- Numbered: `page-1.png`, `page-2.png`, etc.

### Image → PDF

**Supported formats:**
- PNG 8-bit RGB/RGBA non-interlaced
- JPEG baseline

**Process:**
- Lossless embedding (PNG via FlateDecode, JPEG via DCTDecode)
- Size & quality preserved
- Aspect ratio maintained

### Office → PDF

**Tier 1 (LibreOffice headless):**
- Best quality: preserves layout, fonts, images, formatting
- Converts DOCX, XLSX, PPTX to PDF

**Tier 2 (Enhanced fallback):**
- DOCX: detect headings, preserve tables, embed images
- XLSX: render sheets dengan tabel structure & styling
- PPTX: extract slide text & tables

**Tier 3 (Text fallback):**
- Extract text + flatten tables
- Basic PDF output (Courier font)

## Keterbatasan yang perlu diketahui

Bagian ini bukan daftar deficiencies yang tersembunyi, melainkan batas yang
tidak bisa dihilangkan tanpa menulis ulang mesin rendering atau tool eksternal.

### PDF parsing (tier 3 dasar)

- **Ekstraksi teks PDF lebih sederhana daripada pypdf.** PDF yang memakai CJK,
  ligatur, atau font subset tanpa `/ToUnicode` akan menghasilkan teks kosong
  atau salah. Mayoritas PDF hasil scan/Word berbahasa Indonesia aman.
- **Font subset tanpa `/ToUnicode` tidak dapat dipetakan.** Font `Type0`
  (Identity-H) seperti itu menghasilkan teks kosong, bukan karakter pengganti.
- **PDF terenkripsi ditolak** dengan pesan yang jelas. Belum ada dukungan RC4
  maupun AES; hapus proteksi kata sandi lebih dulu.
- **Deteksi tabel turun kualitasnya** dibanding pdfplumber. Tabel ber-grid
  (ada garis) akurat; tabel tanpa garis dideteksi dari jarak antar kata yang
  berulang, jadi bisa salah pada dokumen dengan kolom tidak rapi.

### Formatted backends (tier 2)

- **pdfplumber limitations:** PDF dengan layout kompleks (multi-column, overlapping text) mungkin ekstraknya tidak perfect. Tabel dengan merged cells dideteksi tetapi preserved sebagai flat struktur.
- **Font embedding:** Hanya font standard yang tersimpan di PDF dapat diextract. Custom/embedded fonts fallback ke Times New Roman atau Arial.
- **Images:** Hanya JPEG (`DCTDecode`) yang efisien diextract; image formats lain may be skipped.
- **PPTX table rendering:** Tables diembed sebagai native PPTX objects (editable) tetapi styling (color, border) terbatas pada basic formatting.

### Office to PDF fallback (tier 2 & 3)

- **Enhanced fallback (tier 2) tidak mempertahankan:**
  - Advanced formatting (shadows, gradients, complex styles)
  - Complex graphics atau diagrams
  - Embedded videos atau multimedia
  - Formula Excel hasil komputasi (ditampilkan as text)
  - Floating objects atau text boxes dengan positioning presisi

- **Text fallback (tier 3) menggunakan:**
  - Font Courier (latin-1 support saja; non-Latin characters may fail)
  - Tabel flattened menjadi text rows
  - Gambar dihilangkan
  - Layout flat tanpa spacing kompleks

### Gambar ke PDF

- **PNG requirements:** 8-bit RGB/RGBA, non-interlaced. PNG 16-bit atau interlaced ditolak; simpan ulang sebagai JPEG.
- **JPEG:** Baseline JPEG saja; Progressive JPEG may fail.
- **Size & quality:** Embedded lossless (PNG) atau compressed lossless (JPEG DCTDecode); tidak ada kompresi lossy tambahan.

### Rendering (tier 1 poppler)

- **PDF → Images:** Memerlukan poppler binary (`pdftoppm`). Rendering quality tergantung DPI setting.
- **PDF → PPTX fallback:** Images bukan editable text; untuk edit content perlu tier 2 backend.

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
