# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Interactive Telegram Chatbot with Local LLM & Reminder System

**Nama Dokumen:** PRDCHATBOT  
**Versi:** 1.0 (Archived / Reference Specification)  
**Tanggal:** 13 November 2026  
**Status:** Archived / Dokumentasi Referensi Pengembangan  
**Pemilik Produk:** Pengelola bot Telegram multifungsi  
**Platform:** Python (`python-telegram-bot`), PyTorch, HuggingFace Transformers, SQLite  

---

## 1. Ringkasan Eksekutif & Tujuan Produk

Fitur **Interactive Chatbot** dirancang untuk memberikan asisten percakapan cerdas yang interaktif langsung di dalam bot Telegram multifungsi, dilengkapi kemampuan:
1. **Chat Interaktif Berbasis LLM Lokal:** Menjawab pertanyaan pengguna dengan konteks riwayat percakapan menggunakan model open-source lokal (Qwen2.5-1.5B).
2. **Sistem Pengingat (Reminder Scheduler):** Menjadwalkan pengingat berbasis waktu tertentu (`HH:MM`) dan mengirimkan notifikasi otomatis ke Telegram.
3. **Session & Memory Management:** Mengelola riwayat percakapan pengguna berbasis database lokal (SQLite) dengan batas konteks jendela (sliding context window) yang dapat diatur serta kemampuan reset session.

Dokumen PRD ini mendokumentasikan seluruh spesifikasi fungsional, arsitektur teknis, skema database, konfigurasi prompt, implementasi kode, serta pertimbangan penonaktifan/pencopotan fitur dari bot utama.

---

## 2. Fitur Utama & Spesifikasi Pengguna

### 2.1 Perintah Bot (Command Specifications)

| Perintah | Parameter | Deskripsi | Hak Akses | Contoh Penggunaan |
|---|---|---|---|---|
| `/ask` | `<pertanyaan>` | Mengirimkan pertanyaan ke AI lokal dengan memperhitungkan riwayat chat sebelumnya. | `is_allowed()` (Owner only) | `/ask apa itu machine learning?` |
| `/remind` | `<HH:MM> <pesan>` | Menjadwalkan pesan pengingat pada jam dan menit tertentu (format 24 jam). | `is_allowed()` (Owner only) | `/remind 14:30 Minum air putih` |
| `/reset` | - | Menghapus seluruh riwayat percakapan user di database tanpa menghapus pesan di Telegram. | `is_allowed()` (Owner only) | `/reset` |

### 2.2 Alur Interaksi Pengguna (User Flow)

#### A. Alur Tanya Jawab AI (`/ask`)
```
[User] -> /ask <pertanyaan>
  │
  ├── 1. Validasi Akses: Memastikan user berhak (ALLOWED_USER_ID)
  ├── 2. Status Indicator: Bot mengirim pesan "🤔 Memproses pertanyaan..."
  ├── 3. Retrieval Konteks: Mengambil N pesan terakhir (default: 10) dari SQLite
  ├── 4. Prompt Assembly: Menggabungkan System Prompt + History + User Message
  ├── 5. Inferensi LLM: Model Qwen2.5-1.5B memproses di background thread (asyncio.to_thread)
  ├── 6. Penyimpanan Percakapan: Menyimpan query user dan respons AI ke database
  └── 7. Pengiriman Respon: Bot meng-edit status indicator dengan teks jawaban AI
```

#### B. Alur Pengingat (`/remind`)
```
[User] -> /remind 14:30 Rapat Tim
  │
  ├── 1. Validasi Format & Waktu (HH:MM)
  ├── 2. Konversi Timezone: Menggunakan zona waktu lokal (Asia/Jakarta)
  ├── 3. Perhitungan Trigger: Jika waktu sudah lewat hari ini, jadwalkan untuk besok
  ├── 4. Simpan ke SQLite: Masukkan ke tabel `reminders` dengan status `executed=0`
  ├── 5. Konfirmasi ke User: Kirim pesan konfirmasi jadwal reminder
  │
[Background Worker Task]
  ├── Berjalan loop setiap 60 detik (atau via cron)
  ├── Query: SELECT * FROM reminders WHERE executed=0 AND trigger_at <= CURRENT_TIMESTAMP
  ├── Eksekusi: Kirim pesan "⏰ Reminder (HH:MM)\n\n<pesan>" ke chat pengguna
  └── Update Status: Set `executed = 1`
```

---

## 3. Arsitektur Teknis & Struktur Data

### 3.1 Struktur Direktori Modul

```
bot_honey/
├── src/
│   └── chat/
│       ├── __init__.py
│       ├── session.py       # Session history, SQLite manager, & reminder queries
│       └── llm.py           # Wrapper HuggingFace Transformers & PyTorch inference
├── reminders/
│   ├── __init__.py
│   └── worker.py            # Standalone runner untuk cron job reminder
├── prompts/
│   └── system.txt           # File teks kepribadian / system prompt LLM
├── data/
│   └── chat.db              # SQLite storage untuk chat history dan reminder
└── bot.py                   # Handler Telegram PTB & background worker task
```

### 3.2 Skema Database SQLite (`data/chat.db`)

#### Tabel `chat_history`
Menyimpan setiap pesan individual yang dipertukarkan antara pengguna dan asisten.
```sql
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    role TEXT NOT NULL,           -- 'user' atau 'assistant'
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### Tabel `session_metadata`
Mencatat informasi status sesi pengguna dan waktu terakhir kali reset percakapan dilakukan.
```sql
CREATE TABLE IF NOT EXISTS session_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    chat_id INTEGER NOT NULL,
    last_reset DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### Tabel `reminders`
Menyimpan antrean pengingat terjadwal.
```sql
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    trigger_at DATETIME NOT NULL, -- Format ISO-8601 string / datetime
    message TEXT NOT NULL,
    executed INTEGER DEFAULT 0,    -- 0: pending, 1: executed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. Konfigurasi Lingkungan (`.env` & `config.py`)

Variabel environment yang mengatur operasional modul:

| Environment Variable | Nilai Bawaan (Default) | Deskripsi |
|---|---|---|
| `CHAT_DB_PATH` | `data/chat.db` | Jalur file database SQLite untuk chat dan pengingat. |
| `CHAT_LLM_MODEL_PATH` | `models/qwen2.5-1.5b` | Jalur folder model lokal safetensors / HuggingFace. |
| `CHAT_LLM_MAX_TOKENS` | `256` | Batas maksimum token yang dihasilkan oleh model per balasan. |
| `CHAT_LLM_TEMPERATURE` | `0.7` | Derajat variasi kreativitas inferensi (0.0 - 1.0). |
| `CHAT_LLM_TOP_P` | `0.9` | Ambang batas nucleus sampling (0.0 - 1.0). |
| `CHAT_CONTEXT_WINDOW` | `10` | Jumlah pesan riwayat sebelumnya yang dimuat ke prompt AI. |

### System Prompt Default (`prompts/system.txt`)
```text
Anda adalah asisten AI yang sangat membantu dan interaktif. Anda dapat memahami konteks dari percakapan sebelumnya dan memberikan jawaban yang relevan dan bermanfaat. Selalu bersikap ramah, jujur, dan membantu.
```

---

## 5. Dependensi Python & Kebutuhan Resource

### Dependensi Khusus Modul
- `torch==2.0.0`
- `transformers==4.30.0`
- `sentencepiece==0.1.99`

### Karakteristik Resource & Hardware
- **Model Dasar:** Qwen2.5-1.5B (Causal Language Model)
- **RAM / VRAM Footprint:** ~3.5 GB hingga 6 GB saat inisialisasi bobot model di memori.
- **Inference Mode:**
  - GPU (CUDA): `torch.float16`
  - CPU Mode: `torch.float32` (latensi lebih lambat ~3-8 detik per respons pada CPU biasa).

---

## 6. Arsip Implementasi Kode (Full Source Code Reference)

Untuk keperluan referensi di masa mendatang, seluruh kode implementasi diarsipkan di bawah ini:

### 6.1 `src/chat/session.py`
```python
"""
Chat session manager - handles conversation history storage and retrieval
"""
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ChatSession:
    """Manages chat history and session state for individual users"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                chat_id INTEGER NOT NULL,
                last_reset DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                trigger_at DATETIME NOT NULL,
                message TEXT NOT NULL,
                executed INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_message(self, user_id: int, chat_id: int, role: str, content: str) -> None:
        """Add a message to chat history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO chat_history (user_id, chat_id, role, content)
                VALUES (?, ?, ?, ?)
            """, (user_id, chat_id, role, content))
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding message: {e}")
        finally:
            conn.close()
    
    def get_history(self, user_id: int, chat_id: int, limit: int = 10) -> List[Dict[str, str]]:
        """Get chat history for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT role, content FROM chat_history
                WHERE user_id = ? AND chat_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (user_id, chat_id, limit))
            rows = cursor.fetchall()
            return [{"role": row[0], "content": row[1]} for row in rows]
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
        finally:
            conn.close()
    
    def reset_session(self, user_id: int) -> bool:
        """Clear all chat history for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
            cursor.execute("""
                UPDATE session_metadata
                SET last_reset = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            logger.info(f"Session reset for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error resetting session: {e}")
            return False
        finally:
            conn.close()
    
    def add_reminder(self, user_id: int, chat_id: int, trigger_at: str, message: str) -> bool:
        """Add a reminder"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO reminders (user_id, chat_id, trigger_at, message)
                VALUES (?, ?, ?, ?)
            """, (user_id, chat_id, trigger_at, message))
            conn.commit()
            logger.info(f"Reminder added for user {user_id}: {message}")
            return True
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return False
        finally:
            conn.close()
    
    def get_pending_reminders(self) -> List[Dict[str, Any]]:
        """Get all pending reminders that should be executed now"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, user_id, chat_id, message FROM reminders
                WHERE executed = 0 AND trigger_at <= CURRENT_TIMESTAMP
                ORDER BY trigger_at ASC
            """)
            rows = cursor.fetchall()
            reminders = []
            for row in rows:
                reminders.append({
                    "id": row[0],
                    "user_id": row[1],
                    "chat_id": row[2],
                    "message": row[3]
                })
            return reminders
        except Exception as e:
            logger.error(f"Error getting pending reminders: {e}")
            return []
        finally:
            conn.close()
    
    def mark_reminder_executed(self, reminder_id: int) -> bool:
        """Mark a reminder as executed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE reminders SET executed = 1 WHERE id = ?
            """, (reminder_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error marking reminder as executed: {e}")
            return False
        finally:
            conn.close()
```

### 6.2 `src/chat/llm.py`
```python
"""
Local LLM integration for chat responses
Handles inference with Qwen2.5-1.5B model
"""
import logging
import torch
from typing import List, Dict, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM

logger = logging.getLogger(__name__)


class LLMChat:
    """Wrapper for local LLM inference"""
    
    def __init__(self, model_path: str, max_tokens: int = 256, temperature: float = 0.7, top_p: float = 0.9):
        self.model_path = model_path
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.model = None
        self.tokenizer = None
        self.device = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load model and tokenizer"""
        try:
            logger.info(f"Loading model from {self.model_path}...")
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"Using device: {self.device}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                trust_remote_code=True,
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
                device_map="auto"
            )
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def build_prompt(self, system_prompt: str, history: List[Dict[str, str]], user_message: str) -> str:
        """Build prompt from system message, history, and current message"""
        lines = [system_prompt, ""]
        for msg in history:
            if msg["role"] == "user":
                lines.append(f"User: {msg['content']}")
            elif msg["role"] == "assistant":
                lines.append(f"Assistant: {msg['content']}")
        lines.append(f"User: {user_message}")
        lines.append("Assistant:")
        return "\n".join(lines)
    
    def generate(self, system_prompt: str, history: List[Dict[str, str]], user_message: str) -> str:
        """Generate response from model"""
        try:
            prompt = self.build_prompt(system_prompt, history, user_message)
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs.input_ids,
                    attention_mask=inputs.attention_mask,
                    max_new_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            if "Assistant:" in response:
                response = response.split("Assistant:")[-1].strip()
            
            response = response.rstrip()
            if response and response[-1] not in ".!?":
                for punct in ".!?":
                    if punct in response:
                        response = response.rsplit(punct, 1)[0] + punct
            return response
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Maaf, terjadi kesalahan saat memproses jawaban: {str(e)}"
```

### 6.3 `reminders/worker.py`
```python
#!/usr/bin/env python3
"""
Reminder worker - run periodically by cron to send reminders
Usage: python reminders/worker.py
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import Bot
from config import CHAT_DB_PATH, ALLOWED_USER_ID, TIMEZONE, TELEGRAM_BOT_TOKEN
from src.chat.session import ChatSession

load_dotenv()

async def send_reminders() -> None:
    session = ChatSession(str(CHAT_DB_PATH))
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    reminders = session.get_pending_reminders()
    if not reminders:
        return
    for reminder in reminders:
        user_id = reminder["user_id"]
        chat_id = reminder["chat_id"]
        message = reminder["message"]
        reminder_id = reminder["id"]
        tz = ZoneInfo(TIMEZONE)
        now = datetime.now(tz).strftime("%H:%M")
        reminder_text = f"⏰ <b>Reminder ({now})</b>\n\n{message}"
        await bot.send_message(chat_id=chat_id, text=reminder_text, parse_mode="HTML")
        session.mark_reminder_executed(reminder_id)
    await bot.close()

if __name__ == "__main__":
    asyncio.run(send_reminders())
```

---

## 7. Alasan Penonaktifan & Pencopotan (Deprecation Rationale)

1. **Konsumsi Memori Sangat Besar:** Memuat bobot LLM secara lokal via PyTorch dan Transformers menghabiskan RAM/VRAM yang tinggi (3-6 GB), memberatkan host/server atau perangkat mobile (Termux) yang menjalankan bot multifungsi.
2. **Ketergantungan Paket Berat:** `torch`, `transformers`, dan `sentencepiece` menambah beban instalasi dan ukuran lingkungan virtual environment secara signifikan.
3. **Pemisahan Peran (Separation of Concerns):** Bot Telegram multifungsi difokuskan pada utilitas produktivitas (file conversion, downloader, cuaca BMKG, dan statistik suara Discord). Fitur AI interaktif yang lebih terpusat dikelola secara terpisah (misalnya pada arsitektur endpoint OpenAI-compatible / `llama-server` mandiri seperti yang digunakan pada modul Berita).

---

## 8. Kesimpulan

Dokumen ini menjadi rujukan lengkap atas arsitektur, kode sumber, logika database, dan skenario eksekusi fitur Interactive Chatbot & Reminder jika di masa mendatang fitur ini dibutuhkan kembali. Dokumen disimpan dengan aman di root repository sebagai `PRDCHATBOT.md`.
