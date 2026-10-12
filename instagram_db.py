"""Instagram OAuth token storage dengan enkripsi."""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import base64
import logging

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "instagram.db"
DB_PATH.parent.mkdir(exist_ok=True)


def get_cipher():
    """Dapatkan cipher dari .env encryption key."""
    try:
        from config import INSTAGRAM_TOKEN_ENCRYPTION_KEY
        if not INSTAGRAM_TOKEN_ENCRYPTION_KEY:
            raise ValueError("INSTAGRAM_TOKEN_ENCRYPTION_KEY kosong")
        
        # Convert hex string ke bytes, pad ke 44 chars (32 bytes base64)
        key_bytes = bytes.fromhex(INSTAGRAM_TOKEN_ENCRYPTION_KEY)
        # Encode ke base64 dan pad
        key_b64 = base64.urlsafe_b64encode(key_bytes).decode('utf-8')
        if len(key_b64) < 44:
            key_b64 = key_b64.ljust(44, '=')
        return Fernet(key_b64.encode())
    except Exception as e:
        logger.error(f"Cipher init failed: {e}")
        raise


def encrypt_token(token: str) -> str:
    """Enkripsi token sebelum disimpan."""
    try:
        cipher = get_cipher()
        encrypted = cipher.encrypt(token.encode())
        return encrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_token(encrypted: str) -> str:
    """Dekripsi token dari database."""
    try:
        cipher = get_cipher()
        decrypted = cipher.decrypt(encrypted.encode())
        return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise


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
    logger.info(f"Database initialized at {DB_PATH}")


def save_connection(telegram_user_id: int, instagram_user_id: str, 
                   instagram_username: str, access_token: str, expires_in: int = 5184000):
    """Simpan koneksi Instagram."""
    try:
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
        logger.info(f"Saved connection for user {telegram_user_id}: @{instagram_username}")
    except Exception as e:
        logger.error(f"Failed to save connection: {e}")
        raise


def get_connection(telegram_user_id: int) -> dict | None:
    """Ambil koneksi Instagram untuk user Telegram."""
    try:
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
    except Exception as e:
        logger.error(f"Failed to get connection: {e}")
        return None


def delete_connection(telegram_user_id: int):
    """Hapus koneksi Instagram."""
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM instagram_connections WHERE telegram_user_id = ?", (telegram_user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Deleted connection for user {telegram_user_id}")
    except Exception as e:
        logger.error(f"Failed to delete connection: {e}")
        raise


def save_oauth_state(state: str, telegram_user_id: int, code_verifier: str):
    """Simpan state untuk validasi."""
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO oauth_states (state, telegram_user_id, code_verifier)
            VALUES (?, ?, ?)
        """, (state, telegram_user_id, code_verifier))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save oauth state: {e}")
        raise


def get_oauth_state(state: str) -> dict | None:
    """Ambil dan hapus state (one-time use)."""
    try:
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
            cursor.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
            conn.commit()
        
        conn.close()
        
        if not row:
            return None
        
        created_at = datetime.fromisoformat(row[2])
        # State expired setelah 10 menit
        if datetime.utcnow() - created_at > timedelta(minutes=10):
            logger.warning(f"OAuth state expired for user {row[0]}")
            return None
        
        return {
            "telegram_user_id": row[0],
            "code_verifier": row[1],
        }
    except Exception as e:
        logger.error(f"Failed to get oauth state: {e}")
        return None
