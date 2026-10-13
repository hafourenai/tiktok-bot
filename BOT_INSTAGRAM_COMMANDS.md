# Bot Telegram Commands untuk Instagram OAuth

Panduan menambahkan command `/instagram_connect`, `/instagram_status`, dan `/instagram_disconnect` ke bot.py

---

## Part 1: Update bot.py — Import & Setup

### Langkah 1.1 — Tambah import di atas bot.py

Buka bot.py dan cari baris import dari downloader:

```python
from downloader import (
    cleanup_downloads,
    ...
    download_instagram,
    ...
)
```

Ubah menjadi:

```python
from downloader import (
    cleanup_downloads,
    download_tiktok,
    download_with_gallery_dl,
    download_with_tiktok_api_dl,
    download_youtube,
    stalk_tiktok_user,
)
from instagram_oauth import get_auth_url
from instagram_db import get_connection, delete_connection
```

---

## Part 2: Tambah Command Handler

### Langkah 2.1 — Cari bagian akhir bot.py

Cari fungsi `main()` atau `if __name__ == "__main__":`

Sebelum bagian itu, tambahkan command handler baru:

```python
# ============================================================================
# INSTAGRAM OAUTH COMMANDS
# ============================================================================

async def instagram_connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mulai proses login Instagram."""
    if not is_allowed(update):
        await deny(update)
        return
    
    user_id = update.effective_user.id
    message = update.effective_message
    
    # Cek apakah sudah terhubung
    existing = get_connection(user_id)
    if existing:
        await message.reply_text(
            f"✅ Instagram sudah terhubung!\n\n"
            f"Akun: <b>@{existing['instagram_username']}</b>\n\n"
            f"Gunakan /instagram_disconnect untuk logout.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Generate auth URL
    try:
        auth_url = get_auth_url(user_id)
        await message.reply_text(
            "🔐 <b>Login Instagram</b>\n\n"
            "Tekan tombol di bawah untuk login dengan akun Instagram Anda.\n"
            "Anda akan diarahkan ke halaman login resmi Instagram.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Login Instagram", url=auth_url)
            ]])
        )
    except Exception as e:
        logger.error(f"Failed to generate auth URL: {e}")
        await message.reply_text(
            f"❌ Gagal membuat link login.\n\nError: {str(e)}",
            parse_mode=ParseMode.HTML
        )


async def instagram_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cek status koneksi Instagram."""
    if not is_allowed(update):
        await deny(update)
        return
    
    user_id = update.effective_user.id
    message = update.effective_message
    
    connection = get_connection(user_id)
    
    if not connection:
        await message.reply_text(
            "❌ Instagram belum terhubung.\n\n"
            "Gunakan /instagram_connect untuk login.",
            parse_mode=ParseMode.HTML
        )
        return
    
    from datetime import datetime
    expires_at = datetime.fromisoformat(connection['token_expires_at'])
    is_expired = expires_at < datetime.utcnow()
    
    status_emoji = "⚠️" if is_expired else "✅"
    expire_text = f"Expired: {expires_at.strftime('%Y-%m-%d %H:%M')}" if is_expired else f"Exp: {expires_at.strftime('%Y-%m-%d')}"
    
    await message.reply_text(
        f"{status_emoji} <b>Status Instagram</b>\n\n"
        f"Akun: <b>@{connection['instagram_username']}</b>\n"
        f"ID: <code>{connection['instagram_user_id']}</code>\n"
        f"Token: {expire_text}",
        parse_mode=ParseMode.HTML
    )


async def instagram_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logout Instagram."""
    if not is_allowed(update):
        await deny(update)
        return
    
    user_id = update.effective_user.id
    message = update.effective_message
    
    connection = get_connection(user_id)
    if not connection:
        await message.reply_text("❌ Instagram tidak terhubung.")
        return
    
    # Konfirmasi
    await message.reply_text(
        f"⚠️ Yakin ingin logout dari <b>@{connection['instagram_username']}</b>?",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Ya, Logout", callback_data="instagram:confirm_disconnect"),
            InlineKeyboardButton("❌ Batal", callback_data="instagram:cancel_disconnect")
        ]])
    )


async def handle_instagram_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback dari tombol Instagram."""
    query = update.callback_query
    if not is_allowed(update):
        await query.answer("Tidak diizinkan.", show_alert=True)
        return
    
    await query.answer()
    
    if query.data == "instagram:confirm_disconnect":
        user_id = update.effective_user.id
        delete_connection(user_id)
        await query.edit_message_text(
            "✅ Instagram berhasil logout.\n\n"
            "Gunakan /instagram_connect untuk login lagi.",
            parse_mode=ParseMode.HTML
        )
    elif query.data == "instagram:cancel_disconnect":
        await query.edit_message_text("❌ Logout dibatalkan.")
```

---

## Part 2: Daftar Command di main()

### Langkah 2.2 — Update application.add_handler()

Cari bagian di main() yang register command handlers:

```python
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("menu", show_menu))
...
```

Tambahkan sebelum `application.run_polling()`:

```python
application.add_handler(CommandHandler("instagram_connect", instagram_connect))
application.add_handler(CommandHandler("instagram_status", instagram_status))
application.add_handler(CommandHandler("instagram_disconnect", instagram_disconnect))
application.add_handler(CallbackQueryHandler(handle_instagram_callback, pattern="^instagram:"))
```

---

## Part 3: Test Commands

### Langkah 3.1 — Restart bot

```bash
# Hentikan bot lama (Ctrl+C)
# Pastikan callback service sudah berjalan di screen/background lain

cd ~/tiktok-bot
python3 bot.py
```

### Langkah 3.2 — Test di Telegram

Kirim perintah ke bot:

```
/instagram_connect
```

Harusnya bot merespons dengan tombol "🔗 Login Instagram".

---

## Part 4: Test OAuth Flow End-to-End

### Langkah 4.1 — Klik tombol login

1. Di Telegram, klik tombol "🔗 Login Instagram"
2. Anda akan redirect ke halaman login Instagram
3. Login dengan akun Instagram Anda (gunakan akun yang sudah dipilih, minimal follower/verified minimal)
4. Izinkan izin aplikasi
5. Anda akan redirect ke `https://aldidev.tech/auth/instagram/callback`
6. Halaman menampilkan: "✅ Instagram Terhubung! Akun @username berhasil terhubung."
7. Kembali ke Telegram

### Langkah 4.2 — Verifikasi di bot

Kirim:
```
/instagram_status
```

Harusnya menampilkan:
```
✅ Status Instagram

Akun: @username
ID: 12345678
Token: Exp: 2026-12-12
```

---

## Part 5: Troubleshooting

### "Callback tidak bisa diakses"
- Check Cloudflare Tunnel running
- Verify path config di `~/.cloudflared/config.yml`
- Test: `curl https://aldidev.tech/auth/instagram/callback`

### "State not valid atau expired"
- Session OAuth timeout 10 menit
- Coba `/instagram_connect` lagi
- Pastikan waktu server sync dengan internet

### "Instagram username tidak muncul"
- Check Instagram app credentials di Meta Developer
- Pastikan scopes benar: `user_profile,instagram_business_basic_access`
- Coba logout dan connect ulang

### Bot restart, connection hilang?
- Connection disimpan di database `~/tiktok-bot/data/instagram.db`
- Check file ada dan tidak rusak:
  ```bash
  sqlite3 ~/tiktok-bot/data/instagram.db ".tables"
  ```

---

## Part 6: Update Menu Bot (Optional)

Jika ingin Instagram muncul di menu utama, update `menus.py`:

Cari:
```python
def menu_content(section: str):
    ...
    if section == "downloader":
        text = (
            "📥 <b>Media Downloader & Stalker</b>\n\n"
            "• Kirim link <b>TikTok</b> atau <b>YouTube</b>..."
```

Ubah menjadi:
```python
        text = (
            "📥 <b>Media Downloader & Stalker</b>\n\n"
            "• Kirim link <b>TikTok</b> atau <b>YouTube</b> untuk unduh video...\n"
            "• <code>/instagram_connect</code> — Hubungkan Instagram untuk fitur API.\n"
            "• <code>/instagram_status</code> — Cek status koneksi.\n"
            "• <code>/instagram_disconnect</code> — Logout Instagram."
```

---

## Summary

Setelah selesai:

1. ✅ Instagram OAuth flow siap
2. ✅ Token tersimpan aman di database
3. ✅ User bisa login/logout dengan aman
4. ✅ Tidak ada password disimpan di `.env`
5. ✅ Semua login melalui halaman Instagram resmi

**Selamat! Instagram OAuth integration sudah selesai.** 🎉

---

## Next: Integrasi Download Instagram

Sekarang Anda sudah punya token Instagram yang valid. Langkah berikutnya:

1. Gunakan token untuk Instagram Graph API (fitur official)
2. Atau implementasi download publik dengan library alternative

Lihat dokumentasi Instagram Graph API: https://developers.facebook.com/docs/instagram-graph-api
