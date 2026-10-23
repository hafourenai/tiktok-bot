from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .models import ConversationState, JobStatus


def now() -> str:
    return datetime.now(UTC).isoformat()


class Storage:
    """Small transactional SQLite store. Message bodies only live in the short-lived buffer."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, timeout=15, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._db:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    def migrate(self) -> None:
        with self._lock, self._db:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    chat_id INTEGER PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT 'AI_DISABLED',
                    ai_enabled INTEGER NOT NULL DEFAULT 0,
                    enabled_at TEXT,
                    last_incoming_at TEXT,
                    last_manual_reply_at TEXT,
                    latest_message_id INTEGER,
                    message_version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_jobs (
                    job_id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL,
                    message_version INTEGER NOT NULL, execute_at TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_chat ON pending_jobs(chat_id, status);
                CREATE TABLE IF NOT EXISTS message_buffer (
                    chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
                    body TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(chat_id, message_id)
                );
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    chunk_id INTEGER PRIMARY KEY, source TEXT NOT NULL,
                    content TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE,
                    updated_at TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    content, source, chunk_id UNINDEXED
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY, chat_id INTEGER, event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}'
                );
            """)
            # Migration: add ai_enabled/enabled_at columns to existing databases
            for col, definition in (
                ("ai_enabled", "INTEGER NOT NULL DEFAULT 0"),
                ("enabled_at", "TEXT"),
            ):
                try:
                    self._db.execute(
                        f"ALTER TABLE conversations ADD COLUMN {col} {definition}"
                    )
                except sqlite3.OperationalError:
                    pass  # Column already exists

    def ensure_chat(self, chat_id: int) -> sqlite3.Row:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO conversations(chat_id,updated_at) VALUES(?,?)",
                (chat_id, now()),
            )
            return self._db.execute(
                "SELECT * FROM conversations WHERE chat_id=?", (chat_id,)
            ).fetchone()

    def conversation(self, chat_id: int) -> sqlite3.Row:
        return self.ensure_chat(chat_id)

    def set_chat_enabled(self, chat_id: int, enabled: bool) -> None:
        """Enable or disable AI for a specific chat. Called from admin CLI only."""
        state = ConversationState.IDLE if enabled else ConversationState.AI_DISABLED
        with self._lock, self._db:
            self.ensure_chat(chat_id)
            self._db.execute(
                "UPDATE conversations SET ai_enabled=?,enabled_at=?,state=?,"
                "message_version=message_version+1,updated_at=? WHERE chat_id=?",
                (int(enabled), now() if enabled else None, state, now(), chat_id),
            )
            self._clear_chat_locked(chat_id)
            self.audit(chat_id, "AI_ENABLED" if enabled else "AI_DISABLED")

    def buffer_message(self, chat_id: int, message_id: int, body: str, limit: int) -> int:
        with self._lock, self._db:
            self.ensure_chat(chat_id)
            self._db.execute(
                "INSERT INTO message_buffer VALUES(?,?,?,?) ON CONFLICT(chat_id,message_id) "
                "DO UPDATE SET body=excluded.body,created_at=excluded.created_at",
                (chat_id, message_id, body, now()),
            )
            self._db.execute(
                "DELETE FROM message_buffer WHERE chat_id=? AND message_id NOT IN "
                "(SELECT message_id FROM message_buffer WHERE chat_id=? ORDER BY message_id DESC LIMIT ?)",
                (chat_id, chat_id, limit),
            )
            self._db.execute(
                "UPDATE pending_jobs SET status=?,updated_at=? WHERE chat_id=? AND status IN (?,?)",
                (JobStatus.CANCELLED, now(), chat_id, JobStatus.PENDING, JobStatus.PROCESSING),
            )
            self._db.execute(
                "UPDATE conversations SET state=?,last_incoming_at=?,latest_message_id=?,"
                "message_version=message_version+1,updated_at=? WHERE chat_id=?",
                (ConversationState.WAITING, now(), message_id, now(), chat_id),
            )
            row = self._db.execute(
                "SELECT message_version FROM conversations WHERE chat_id=?", (chat_id,)
            ).fetchone()
            return int(row[0])

    def is_duplicate_message(self, chat_id: int, message_id: int, body: str) -> bool:
        with self._lock:
            row = self._db.execute(
                "SELECT body FROM message_buffer WHERE chat_id=? AND message_id=?",
                (chat_id, message_id),
            ).fetchone()
            return bool(row and row[0] == body)

    def delete_messages(self, chat_id: int, message_ids: list[int]) -> bool:
        if not message_ids:
            return False
        placeholders = ",".join("?" for _ in message_ids)
        with self._lock, self._db:
            cursor = self._db.execute(
                f"DELETE FROM message_buffer WHERE chat_id=? AND message_id IN ({placeholders})",
                (chat_id, *message_ids),
            )
            if not cursor.rowcount:
                return False
            self._db.execute("DELETE FROM message_buffer WHERE chat_id=?", (chat_id,))
            self._db.execute(
                "UPDATE pending_jobs SET status=?,updated_at=? WHERE chat_id=? AND status IN (?,?)",
                (JobStatus.CANCELLED, now(), chat_id, JobStatus.PENDING, JobStatus.PROCESSING),
            )
            self._db.execute(
                "UPDATE conversations SET state=?,message_version=message_version+1,updated_at=? WHERE chat_id=?",
                (ConversationState.IDLE, now(), chat_id),
            )
            return True

    def messages(self, chat_id: int, max_chars: int) -> str:
        with self._lock:
            rows = self._db.execute(
                "SELECT body FROM message_buffer WHERE chat_id=? ORDER BY message_id", (chat_id,)
            ).fetchall()
        return "\n".join(row[0] for row in rows)[-max_chars:]

    def create_job(self, chat_id: int, version: int, execute_at: str) -> str:
        job_id = uuid.uuid4().hex
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO pending_jobs VALUES(?,?,?,?,?,?,?)",
                (job_id, chat_id, version, execute_at, JobStatus.PENDING, now(), now()),
            )
        return job_id

    def claim_job(self, job_id: str, chat_id: int, version: int) -> bool:
        with self._lock, self._db:
            valid = self._db.execute(
                "SELECT 1 FROM conversations c JOIN pending_jobs j ON j.chat_id=c.chat_id "
                "WHERE j.job_id=? AND c.chat_id=? AND j.status=? AND c.message_version=? "
                "AND c.ai_enabled=1 AND c.state=?",
                (job_id, chat_id, JobStatus.PENDING, version, ConversationState.WAITING),
            ).fetchone()
            if not valid:
                return False
            self._db.execute(
                "UPDATE pending_jobs SET status=?,updated_at=? WHERE job_id=?",
                (JobStatus.PROCESSING, now(), job_id),
            )
            self._db.execute(
                "UPDATE conversations SET state=?,updated_at=? WHERE chat_id=?",
                (ConversationState.AI_PROCESSING, now(), chat_id),
            )
            return True

    def can_send(self, job_id: str, chat_id: int, version: int) -> bool:
        with self._lock:
            return bool(self._db.execute(
                "SELECT 1 FROM conversations c JOIN pending_jobs j ON j.chat_id=c.chat_id "
                "WHERE j.job_id=? AND c.chat_id=? AND j.status=? AND c.message_version=? "
                "AND c.ai_enabled=1 AND c.state=?",
                (job_id, chat_id, JobStatus.PROCESSING, version, ConversationState.AI_PROCESSING),
            ).fetchone())

    def finish_job(self, job_id: str, chat_id: int, sent: bool) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE pending_jobs SET status=?,updated_at=? WHERE job_id=?",
                (JobStatus.SENT if sent else JobStatus.FAILED, now(), job_id),
            )
            if sent:
                self._db.execute(
                    "UPDATE conversations SET state=?,updated_at=? WHERE chat_id=?",
                    (ConversationState.AI_ACTIVE, now(), chat_id),
                )
                self._db.execute("DELETE FROM message_buffer WHERE chat_id=?", (chat_id,))

    def human_handoff(self, chat_id: int, event_type: str = "HUMAN_REPLY") -> None:
        with self._lock, self._db:
            self.ensure_chat(chat_id)
            self._db.execute(
                "UPDATE conversations SET state=?,last_manual_reply_at=?,"
                "message_version=message_version+1,updated_at=? WHERE chat_id=?",
                (ConversationState.HUMAN_ACTIVE, now(), now(), chat_id),
            )
            self._clear_chat_locked(chat_id)
            self.audit(chat_id, event_type)

    def resume(self, chat_id: int) -> None:
        with self._lock, self._db:
            row = self.ensure_chat(chat_id)
            state = ConversationState.IDLE if row["ai_enabled"] else ConversationState.AI_DISABLED
            self._db.execute(
                "UPDATE conversations SET state=?,updated_at=? WHERE chat_id=?",
                (state, now(), chat_id),
            )

    def cancel_all_stale_jobs(self) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE pending_jobs SET status=?,updated_at=? WHERE status IN (?,?)",
                (JobStatus.CANCELLED, now(), JobStatus.PENDING, JobStatus.PROCESSING),
            )
            self._db.execute(
                "UPDATE conversations SET state=?,updated_at=? WHERE state IN (?,?)",
                (ConversationState.IDLE, now(), ConversationState.WAITING, ConversationState.AI_PROCESSING),
            )
            self._db.execute("DELETE FROM message_buffer")

    def delay(self, default: int) -> int:
        with self._lock:
            row = self._db.execute("SELECT value FROM settings WHERE key='auto_reply_delay'").fetchone()
            return int(row[0]) if row else default

    def set_delay(self, seconds: int) -> None:
        if seconds < 1:
            raise ValueError("Delay minimal 1 detik")
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO settings(key,value) VALUES('auto_reply_delay',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(seconds),),
            )

    def list_chats(self) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(
                "SELECT chat_id,state,ai_enabled,enabled_at,updated_at "
                "FROM conversations ORDER BY updated_at DESC"
            ).fetchall()

    def audit(self, chat_id: int | None, event_type: str, metadata: dict | None = None) -> None:
        self._db.execute(
            "INSERT INTO audit_events(chat_id,event_type,created_at,metadata) VALUES(?,?,?,?)",
            (chat_id, event_type, now(), json.dumps(metadata or {}, separators=(",", ":"))),
        )

    def _clear_chat_locked(self, chat_id: int) -> None:
        self._db.execute("DELETE FROM message_buffer WHERE chat_id=?", (chat_id,))
        self._db.execute(
            "UPDATE pending_jobs SET status=?,updated_at=? WHERE chat_id=? AND status IN (?,?)",
            (JobStatus.CANCELLED, now(), chat_id, JobStatus.PENDING, JobStatus.PROCESSING),
        )

    def close(self) -> None:
        with self._lock:
            self._db.close()
