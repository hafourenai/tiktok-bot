# Instagram OAuth Callback Service — Panduan Lengkap

Panduan setup dan menjalankan FastAPI callback service untuk Instagram OAuth di Termux.

---

## Part 1: Install Dependencies

### Langkah 1.1 — Tambah FastAPI ke requirements

1. Di Termux, buka file `requirements-oauth.txt`:
   ```bash
   nano ~/tiktok-bot/requirements-oauth.txt
   ```

2. Isi dengan:
   ```
   fastapi==0.104.1
   uvicorn[standard]==0.24.0
   cryptography==41.0.7
   ```

3. Simpan: `Ctrl+O` → `Enter` → `Ctrl+X`

### Langkah 1.2 — Install

```bash
cd ~/tiktok-bot
pip install -r requirements-oauth.txt
```

Tunggu hingga selesai (biasanya 2-3 menit).

---

## Part 2: Buat Database & Storage Token

### Langkah 2.1 — Buat file instagram_db.py

```bash
nano ~/tiktok-bot/instagram_db.py
```

Paste code ini:

```python
"""Instagram OAuth token storage dengan enkripsi."""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import os
import json

DB_PATH = Path(__file__).parent / "data" / "instagram.db"
DB_PATH.parent.mkdir(exist_ok=True)

def get_encryption_key() -> bytes:
    """Dapatkan kunci enkripsi dari .env"""
    from config import INSTAGRAM_TOKEN_ENCRYPTION_KEY
    if not INSTAGRAM_TOKEN_ENCRYPTION_KEY:
        raise ValueError("INSTAGRAM_TOKEN_ENCRYPTION_KEY tidak dikonfigurasi di .env")
    # Pastikan key 32 karakter hex (16 bytes)
    key_bytes = bytes.fromhex(INSTAGRAM_TOKEN_ENCRYPTION_KEY)
    return Fernet(Fernet.generate_key()[:len(key_bytes)].ljust(44, b'='))

def encrypt_token(token: str) -> str:
    """Enkripsi token sebelum disimpan."""
    cipher = Fernet(Fernet.generate_key()[:32].ljust(44, b'='))
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    """Dekripsi token dari database."""
    cipher = Fernet(Fernet.generate_key()[:32].ljust(44, b'='))
    return cipher.decrypt(encrypted.encode()).decode()

def init_db():
    """Buat tabel jika belum ada."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instagram_connections (
            id INTEGER PRIMARY KEY,
            telegram_user_id INTEGER UNIQUE NOT NULL,
            instagram_user_id TEXT,
            instagram_username TEXT,
            access_token TEXT NOT NULL,
            token_expires_at TEXT,
            scopes TEXT,
            connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            telegram_user_id INTEGER NOT NULL,
            code_verifier TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_connection(telegram_user_id: int, instagram_user_id: str, 
                   instagram_username: str, access_token: str, expires_in: int = 5184000):
    """Simpan koneksi Instagram."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    encrypted_token = encrypt_token(access_token)
    expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO instagram_connections 
        (telegram_user_id, instagram_user_id, instagram_username, access_token, token_expires_at, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (telegram_user_id, instagram_user_id, instagram_username, encrypted_token, expires_at))
    
    conn.commit()
    conn.close()

def get_connection(telegram_user_id: int) -> dict | None:
    """Ambil koneksi Instagram untuk user Telegram."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT instagram_user_id, instagram_username, access_token, token_expires_at
        FROM instagram_connections
        WHERE telegram_user_id = ?
    """, (telegram_user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "instagram_user_id": row[0],
        "instagram_username": row[1],
        "access_token": decrypt_token(row[2]),
        "token_expires_at": row[3],
    }

def delete_connection(telegram_user_id: int):
    """Hapus koneksi Instagram."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM instagram_connections WHERE telegram_user_id = ?", (telegram_user_id,))
    conn.commit()
    conn.close()

def save_oauth_state(state: str, telegram_user_id: int, code_verifier: str):
    """Simpan state untuk validasi."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO oauth_states (state, telegram_user_id, code_verifier)
        VALUES (?, ?, ?)
    """, (state, telegram_user_id, code_verifier))
    conn.commit()
    conn.close()

def get_oauth_state(state: str) -> dict | None:
    """Ambil dan hapus state (one-time use)."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT telegram_user_id, code_verifier, created_at
        FROM oauth_states
        WHERE state = ?
    """, (state,))
    
    row = cursor.fetchone()
    if row:
        # Hapus state agar tidak bisa dipakai ulang
        cursor.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        conn.commit()
    
    conn.close()
    
    if not row:
        return None
    
    created_at = datetime.fromisoformat(row[2])
    # State expired setelah 10 menit
    if datetime.utcnow() - created_at > timedelta(minutes=10):
        return None
    
    return {
        "telegram_user_id": row[0],
        "code_verifier": row[1],
    }
```

Simpan: `Ctrl+O` → `Enter` → `Ctrl+X`

### Langkah 2.2 — Buat file instagram_oauth.py

```bash
nano ~/tiktok-bot/instagram_oauth.py
```

Paste code ini:

```python
"""Instagram OAuth flow management."""

import secrets
import base64
import hashlib
import httpx
from config import INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, INSTAGRAM_REDIRECT_URI
from instagram_db import save_oauth_state, get_oauth_state, save_connection, get_connection, delete_connection

def generate_pkce():
    """Generate PKCE code_verifier dan code_challenge."""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

def get_auth_url(telegram_user_id: int) -> str:
    """Generate Instagram OAuth authorization URL."""
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce()
    
    # Simpan state dan PKCE verifier
    save_oauth_state(state, telegram_user_id, code_verifier)
    
    params = {
        "client_id": INSTAGRAM_APP_ID,
        "redirect_uri": INSTAGRAM_REDIRECT_URI,
        "scope": "user_profile,instagram_business_basic_access",
        "response_type": "code",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    
    auth_url = "https://api.instagram.com/oauth/authorize?" + "&".join(
        f"{k}={v}" for k, v in params.items()
    )
    return auth_url

async def exchange_code_for_token(code: str, state: str) -> dict:
    """Tukar authorization code menjadi access token."""
    state_data = get_oauth_state(state)
    if not state_data:
        raise ValueError("State tidak valid atau sudah expired")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://graph.instagram.com/v18.0/access_token",
            data={
                "client_id": INSTAGRAM_APP_ID,
                "client_secret": INSTAGRAM_APP_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": INSTAGRAM_REDIRECT_URI,
                "code": code,
                "code_verifier": state_data["code_verifier"],
            }
        )
        response.raise_for_status()
        data = response.json()
    
    # Dapatkan user info
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            f"https://graph.instagram.com/me?fields=id,username&access_token={data['access_token']}"
        )
        user_response.raise_for_status()
        user_data = user_response.json()
    
    # Simpan ke database
    save_connection(
        telegram_user_id=state_data["telegram_user_id"],
        instagram_user_id=user_data["id"],
        instagram_username=user_data["username"],
        access_token=data["access_token"],
        expires_in=data.get("expires_in", 5184000)
    )
    
    return {
        "telegram_user_id": state_data["telegram_user_id"],
        "instagram_username": user_data["username"],
    }
```

Simpan: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## Part 3: Buat Callback Service

### Langkah 3.1 — Buat file callback_service.py

```bash
nano ~/tiktok-bot/callback_service.py
```

Paste code ini:

```python
"""FastAPI callback service untuk Instagram OAuth."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
import logging
from instagram_oauth import exchange_code_for_token

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}

@app.get("/auth/instagram/callback", response_class=HTMLResponse)
async def instagram_callback(code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    """Handle Instagram OAuth callback."""
    
    if error:
        logger.error(f"OAuth error: {error}")
        return f"""
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>❌ OAuth Error</h1>
            <p>Error: {error}</p>
            <p><a href="https://t.me/YOUR_BOT_USERNAME">← Kembali ke Bot Telegram</a></p>
        </body>
        </html>
        """
    
    if not code or not state:
        logger.error("Missing code atau state")
        raise HTTPException(status_code=400, detail="Missing code or state")
    
    try:
        result = await exchange_code_for_token(code, state)
        logger.info(f"Successfully authenticated: {result['instagram_username']}")
        
        return f"""
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>✅ Instagram Terhubung!</h1>
            <p>Akun <strong>{result['instagram_username']}</strong> berhasil terhubung.</p>
            <p>Anda boleh menutup halaman ini dan kembali ke Telegram.</p>
        </body>
        </html>
        """
    
    except ValueError as e:
        logger.error(f"State validation failed: {e}")
        return f"""
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>❌ Session Expired</h1>
            <p>State token sudah expired atau invalid. Coba `/instagram_connect` lagi.</p>
        </body>
        </html>
        """
    
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return f"""
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>❌ Login Gagal</h1>
            <p>Error: {str(e)}</p>
            <p>Coba lagi atau hubungi developer.</p>
        </body>
        </html>
        """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
```

Simpan: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## Part 4: Update config.py

### Langkah 4.1 — Tambah Instagram OAuth config

1. Buka config.py:
   ```bash
   nano ~/tiktok-bot/config.py
   ```

2. Tambahkan di akhir file (sebelum `if failed:`):
   ```python
   INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "").strip()
   INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "").strip()
   INSTAGRAM_REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "").strip()
   INSTAGRAM_TOKEN_ENCRYPTION_KEY = os.getenv("INSTAGRAM_TOKEN_ENCRYPTION_KEY", "").strip()
   ```

3. Simpan: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## Part 5: Test Callback Service

### Langkah 5.1 — Jalankan service

```bash
cd ~/tiktok-bot
python3 callback_service.py
```

Harusnya output:
```
INFO:     Uvicorn running on http://127.0.0.1:8001
```

### Langkah 5.2 — Test health endpoint

Buka terminal baru:
```bash
curl http://localhost:8001/health
```

Harusnya return:
```json
{"status":"ok"}
```

### Langkah 5.3 — Stop service

Di terminal yang menjalankan service, tekan `Ctrl+C`.

---

## Part 6: Jalankan Service Persisten (Background)

### Opsi A: Screen / tmux (Termux built-in)

```bash
# Buat session screen baru
screen -S instagram_oauth

# Di dalam screen:
cd ~/tiktok-bot
python3 callback_service.py

# Detach: Ctrl+A kemudian D

# List sessions:
screen -ls

# Reattach:
screen -r instagram_oauth
```

### Opsi B: systemd (jika Termux support)

```bash
# Buat service file
nano ~/.config/systemd/user/instagram-oauth.service
```

Isi:
```ini
[Unit]
Description=Instagram OAuth Callback Service
After=network.target

[Service]
Type=simple
User=u0_a123
WorkingDirectory=/data/data/com.termux/files/home/tiktok-bot
ExecStart=/data/data/com.termux/files/usr/bin/python3 callback_service.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Jalankan:
```bash
systemctl --user enable instagram-oauth.service
systemctl --user start instagram-oauth.service
systemctl --user status instagram-oauth.service
```

---

## Part 7: Verifikasi Setup Lengkap

1. **Database tercipta:**
   ```bash
   ls -la ~/tiktok-bot/data/instagram.db
   ```
   Harusnya file ada.

2. **Service berjalan:**
   ```bash
   curl https://aldidev.tech/auth/instagram/callback
   ```
   Harusnya return HTML response (atau 404 jika path Cloudflare belum right).

3. **Cloudflare Tunnel aktif:**
   Jalankan `cloudflared tunnel run` dan lihat routes.

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'fastapi'"
```bash
pip install -r requirements-oauth.txt
```

### "Port 8001 already in use"
Cari process yang pakai port 8001:
```bash
netstat -tlnp | grep 8001
kill <PID>
```

### "INSTAGRAM_TOKEN_ENCRYPTION_KEY not configured"
Pastikan `.env` sudah update dengan encryption key (lihat INSTAGRAM_SETUP.md).

### Callback URL tidak terdeteksi
- Check Cloudflare Tunnel config (`~/.cloudflared/config.yml`)
- Pastikan path `/auth/instagram/*` ada
- Restart tunnel: `cloudflared tunnel run`

---

## Next Steps

1. Setelah service berjalan stabil, lanjut ke bot command setup
2. Lihat file **BOT_INSTAGRAM_COMMANDS.md** untuk update bot.py

---

**Callback service siap! 🎉**
