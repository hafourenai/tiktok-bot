# 🍽️ Menu Image Generator Integration

Menu image generator telah berhasil di-integrate ke dalam `telegram_personal_ai`.

## 📋 Apa yang sudah diimplementasi

### 1. **`app/menu_generator.py`** - Menu Image Generator
- Fetch data dari catalog items
- Filter stok > 0 & aktif = TRUE
- Group items by kategori
- Generate gambar PNG yang menarik dengan PIL
- Smart cache (hanya regenerate jika ada perubahan stok)

### 2. **`app/service.py`** - Menu Detection & Processing
- `_is_menu_request()` - Detect keyword menu dari user
- `get_menu_image_path()` - Generate & get menu image path
- Keywords yang dikenali:
  - "menu nya apa saja?"
  - "apa menu?"
  - "menu hari ini"
  - "daftar menu"
  - "menunya"
  - "pricelist"
  - "menu" (standalone)

### 3. **`app/telegram_app.py`** - Image Sender
- `send_menu_image()` - Kirim image ke user via Telethon
- Integration ke `on_incoming()` handler
- Auto-detect menu request dan bypass AI processing

## 🚀 Cara Kerja

```
User: "menu nya apa saja?"
       ↓
TelegramApp.on_incoming() detects menu request
       ↓
service.get_menu_image_path() returns image path
       ↓
TelegramApp.send_menu_image() sends PNG to user
       ↓
User melihat menu gambar yang menarik!
```

## 📁 File Structure

```
telegram_personal_ai/
├── app/
│   ├── menu_generator.py      [NEW] Menu image generator
│   ├── service.py             [UPDATED] Menu detection
│   ├── telegram_app.py        [UPDATED] Image sender
│   └── catalog.py             [EXISTING] Data source
└── public/
    └── menu.png               [AUTO-GENERATED] Menu image
```

## ⚙️ Configuration

Tidak perlu setup tambahan. Semua automatic:
- MenuGenerator di-initialize di `AssistantService.__init__()`
- Menu keywords otomatis ter-detect di `on_incoming()`
- Image otomatis ter-generate saat ada request
- Cache otomatis ter-update saat ada perubahan stok

## 🧪 Testing

Tested dengan:
- ✅ MenuGenerator import
- ✅ AssistantService import
- ✅ Menu image generation dengan sample data
- ✅ Stok filtering (0 items difilter keluar)

## 📝 Keywords yang Trigger Menu Image

Regex patterns:
```python
r'menu.*apa\s*saja'       # "menu apa saja", "menu nya apa saja"
r'apa.*menu'              # "apa menu", "apa menunya"
r'menu\s*hari\s*ini'      # "menu hari ini"
r'^\s*menu\s*$'           # "menu" (standalone)
r'daftar\s*menu'          # "daftar menu"
r'menunya'                # "menunya"
r'pricelist'              # "pricelist"
```

Case-insensitive dan stripped.

## 🎨 Menu Image Features

- **12 Kategori** dengan warna berbeda
- **Nama item + Harga dalam Rp**
- **Status ketersediaan** untuk setiap item
- **Auto-filtering stok** = 0
- **Timestamp update** di footer
- **Responsive height** (auto-adjust sesuai jumlah item)

## 🔄 Auto-Update Stok

Tidak perlu setup polling manual. Setiap kali user request menu:
1. Fetch data terbaru dari catalog
2. Check hash dengan cache
3. Jika ada perubahan → regenerate image
4. Jika tidak ada perubahan → gunakan cached image

## ❌ Troubleshooting

**Menu tidak muncul saat user ketik "menu nya apa saja?"**
- Check apakah catalog enabled di settings
- Check apakah ada items dengan stok > 0

**Gambar error/tidak muncul**
- Check folder `public/` ada
- Check error logs untuk detail

**Stok tidak ter-update**
- Cache di-clear otomatis saat ada perubahan
- Tunggu ~1 menit untuk refresh

## 📊 Data Flow

```
Google Sheets (catalog_csv_url)
         ↓
catalog.items() fetch
         ↓
MenuGenerator.generate() process
         ↓
public/menu.png (generated)
         ↓
service.get_menu_image_path() read
         ↓
telegram_app.send_menu_image() send
         ↓
User chat (Telegram)
```

---

## 🎯 Next Steps

1. **Ensure** `catalog_csv_url` diset di `.env` untuk telegram_personal_ai
2. **Test** dengan ketik "menu nya apa saja?" ke bot
3. **Monitor** logs untuk tracking

Semuanya sudah siap! 🚀
