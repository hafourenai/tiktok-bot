# Instagram OAuth Setup — Checklist & Quick Reference

Panduan cepat untuk mengikuti seluruh setup Instagram OAuth.

---

## ✅ Checklist Setup

### Phase 1: Meta Developer Setup
- [ ] Daftar Meta Developer Account (https://developers.facebook.com)
- [ ] Buat aplikasi baru dengan nama "Honey Instagram Downloader"
- [ ] Tambah Instagram product ke aplikasi
- [ ] Setup Instagram Login settings
- [ ] Dapatkan App ID dan App Secret

**File referensi:** `INSTAGRAM_SETUP.md`

---

### Phase 2: Konfigurasi Termux
- [ ] Generate encryption key: `python3 -c "import secrets; print(secrets.token_hex(16))"`
- [ ] Update `.env` dengan:
  - `INSTAGRAM_APP_ID=...`
  - `INSTAGRAM_APP_SECRET=...`
  - `INSTAGRAM_REDIRECT_URI=https://aldidev.tech/auth/instagram/callback`
  - `INSTAGRAM_TOKEN_ENCRYPTION_KEY=...`
- [ ] Verifikasi config: `python3 -c "from config import INSTAGRAM_APP_ID; print('OK' if INSTAGRAM_APP_ID else 'FAIL')"`

**File referensi:** `INSTAGRAM_SETUP.md` (Part 4)

---

### Phase 3: Cloudflare Tunnel Update
- [ ] Backup config: `cp ~/.cloudflared/config.yml ~/.cloudflared/config.yml.backup`
- [ ] Update `~/.cloudflared/config.yml` dengan path routing untuk `/auth/instagram/*` → port 8001
- [ ] Restart Cloudflare Tunnel: `cloudflared tunnel run`
- [ ] Test: `curl -I https://aldidev.tech/auth/instagram/callback`

**File referensi:** `CLOUDFLARE_TUNNEL_UPDATE.md`

---

### Phase 4: Install Dependencies
- [ ] Buat `requirements-oauth.txt` dengan FastAPI, Uvicorn, Cryptography
- [ ] Install: `pip install -r requirements-oauth.txt`

**File referensi:** `CALLBACK_SERVICE.md` (Part 1)

---

### Phase 5: Buat Database & OAuth Module
- [ ] Buat `instagram_db.py` — token storage dengan enkripsi
- [ ] Buat `instagram_oauth.py` — PKCE + OAuth flow
- [ ] Test database creation: `python3 -c "from instagram_db import init_db; init_db(); print('OK')"`

**File referensi:** `CALLBACK_SERVICE.md` (Part 2)

---

### Phase 6: Buat Callback Service
- [ ] Buat `callback_service.py` — FastAPI endpoint
- [ ] Test lokal: `python3 callback_service.py` → `curl http://localhost:8001/health`
- [ ] Setup persistent running (screen atau systemd)

**File referensi:** `CALLBACK_SERVICE.md` (Part 3-6)

---

### Phase 7: Update Bot
- [ ] Update import di `bot.py`: tambah `instagram_oauth`, `instagram_db`
- [ ] Tambah command handlers: `instagram_connect`, `instagram_status`, `instagram_disconnect`
- [ ] Daftar handlers di `main()`
- [ ] Update `config.py` dengan Instagram OAuth settings
- [ ] Test: `/instagram_connect` di Telegram

**File referensi:** `BOT_INSTAGRAM_COMMANDS.md`

---

### Phase 8: End-to-End Test
- [ ] Pastikan callback_service berjalan
- [ ] Pastikan Cloudflare Tunnel aktif
- [ ] Kirim `/instagram_connect` ke bot
- [ ] Klik tombol login → login di Instagram → redirect callback
- [ ] Verify connection: `/instagram_status`
- [ ] Test disconnect: `/instagram_disconnect`

---

## 📋 File yang Perlu Dibuat/Diupdate

| File | Type | Status | Size |
|------|------|--------|------|
| `.env` | Update | Tambah OAuth credentials | ~200 bytes |
| `config.py` | Update | Tambah OAuth config | +10 lines |
| `instagram_db.py` | Create | Token storage | ~250 lines |
| `instagram_oauth.py` | Create | OAuth flow | ~120 lines |
| `callback_service.py` | Create | FastAPI service | ~140 lines |
| `bot.py` | Update | Command handlers | +150 lines |
| `requirements-oauth.txt` | Create | Dependencies | 3 lines |
| `~/.cloudflared/config.yml` | Update | Tunnel routing | Modify ingress |

---

## ⏱️ Estimasi Waktu

| Phase | Waktu |
|-------|-------|
| Meta Developer setup | 10 menit |
| Cloudflare Tunnel config | 5 menit |
| Database & OAuth module | 10 menit |
| Callback service | 5 menit |
| Bot commands | 10 menit |
| Testing & troubleshooting | 10-20 menit |
| **Total** | **50-70 menit** |

---

## 🚀 Quick Start Commands

```bash
# 1. Generate encryption key
python3 -c "import secrets; print(secrets.token_hex(16))"

# 2. Install dependencies
pip install -r requirements-oauth.txt

# 3. Init database
python3 -c "from instagram_db import init_db; init_db()"

# 4. Run callback service (dalam screen/tmux)
screen -S instagram_oauth
python3 callback_service.py

# 5. Run bot (dalam terminal baru)
python3 bot.py

# 6. Test di Telegram
/instagram_connect
```

---

## 🔍 Verification Commands

```bash
# Check .env configured
grep INSTAGRAM_ ~/.env | grep -v "^#"

# Check database
sqlite3 ~/tiktok-bot/data/instagram.db ".tables"

# Check callback service health
curl http://localhost:8001/health

# Check Cloudflare route
curl -I https://aldidev.tech/auth/instagram/callback

# Check encryption key
python3 -c "from config import INSTAGRAM_TOKEN_ENCRYPTION_KEY; print('✓ Key configured' if INSTAGRAM_TOKEN_ENCRYPTION_KEY else '✗ Key missing')"
```

---

## 📚 Documentation Files

1. **INSTAGRAM_SETUP.md** — Meta Developer registration & credentials
2. **CLOUDFLARE_TUNNEL_UPDATE.md** — Tunnel configuration untuk callback
3. **CALLBACK_SERVICE.md** — FastAPI service setup & running
4. **BOT_INSTAGRAM_COMMANDS.md** — Bot command handlers
5. **INSTAGRAM_OAUTH_SETUP_CHECKLIST.md** — This file

---

## 🆘 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "App ID missing" | Check `.env`, restart Termux |
| "Port 8001 in use" | `killall python3` atau gunakan port berbeda |
| "State expired" | Session timeout 10 min, coba `/instagram_connect` lagi |
| "Callback not found" | Check Cloudflare Tunnel config & restart |
| "Token encrypt error" | Verify encryption key 32 hex chars |
| "Login gagal" | Check App Secret di Meta Developer |

---

## 📞 Support

Jika stuck di tahap tertentu:

1. Baca file dokumentasi yang sesuai (lihat "Documentation Files")
2. Jalankan verification command yang sesuai
3. Check logs di callback service & bot
4. Verify credentials di Meta Developer dashboard

---

**Semua siap? Mulai dari Phase 1: `INSTAGRAM_SETUP.md`** 🚀
