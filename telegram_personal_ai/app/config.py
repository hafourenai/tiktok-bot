from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    if value not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
        raise ValueError(f"{name} harus berupa true/false")
    return value in {"1", "true", "yes", "on"}


def _is_local_url(url: str) -> bool:
    host = urlparse(url).hostname
    if host in {"localhost", None}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session_path: Path
    database_path: Path
    knowledge_dir: Path
    auto_reply_delay: int
    max_buffer_messages: int
    max_buffer_chars: int
    llm_url: str
    llm_model: str
    llm_timeout: float
    llm_max_tokens: int
    llm_temperature: float
    allow_remote_llm: bool
    retrieval_limit: int
    log_level: str
    admin_cli: bool
    spam_window_seconds: int = 60
    spam_warn_threshold: int = 5
    catalog_sheet_id: str = ""
    catalog_sheet_range: str = "Menu!A1:G1000"
    catalog_credentials: Path | None = None
    catalog_cache_seconds: float = 30
    catalog_timeout: float = 15
    catalog_csv_url: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        base = Path(__file__).resolve().parents[1]
        load_dotenv(base / ".env")
        api_id_raw = os.getenv("TG_API_ID", "").strip()
        api_hash = os.getenv("TG_API_HASH", "").strip()
        if not api_id_raw or not api_hash:
            raise ValueError("TG_API_ID dan TG_API_HASH wajib diisi di .env")

        llm_url = os.getenv(
            "LLM_BASE_URL", "http://127.0.0.1:8080/v1/chat/completions"
        ).rstrip("/")
        if llm_url.endswith("/v1"):
            llm_url += "/chat/completions"
        elif not llm_url.endswith("/v1/chat/completions"):
            llm_url += "/v1/chat/completions"
        allow_remote = _bool("LLM_ALLOW_REMOTE", False)
        if not _is_local_url(llm_url) and not allow_remote:
            raise ValueError(
                "LLM endpoint bukan localhost. Set LLM_ALLOW_REMOTE=true hanya jika "
                "pengguna telah diberi tahu bahwa pesannya dikirim ke server eksternal."
            )

        delay = int(os.getenv("AUTO_REPLY_DELAY_SECONDS", "180"))
        if delay < 1:
            raise ValueError("AUTO_REPLY_DELAY_SECONDS minimal 1")
        spam_window = int(os.getenv("SPAM_WINDOW_SECONDS", "60"))
        spam_threshold = int(os.getenv("SPAM_WARN_THRESHOLD", "5"))
        if spam_window < 1 or spam_threshold < 1:
            raise ValueError("SPAM_WINDOW_SECONDS dan SPAM_WARN_THRESHOLD minimal 1")
        cache_seconds = float(os.getenv("CATALOG_CACHE_SECONDS", "30"))
        catalog_timeout = float(os.getenv("CATALOG_TIMEOUT_SECONDS", "15"))
        if cache_seconds < 0 or catalog_timeout <= 0:
            raise ValueError("Cache katalog minimal 0 dan timeout harus positif")
        credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        csv_url = os.getenv("CATALOG_CSV_URL", "").strip()
        if csv_url:
            parsed = urlparse(csv_url)
            if (parsed.scheme != "https" or parsed.hostname != "docs.google.com"
                    or not parsed.path.startswith("/spreadsheets/") or parsed.username or parsed.password):
                raise ValueError("CATALOG_CSV_URL harus berupa URL HTTPS Google Sheets")
        return cls(
            api_id=int(api_id_raw),
            api_hash=api_hash,
            session_path=base / os.getenv("TG_SESSION_PATH", "data/personal_session"),
            database_path=base / os.getenv("DATABASE_PATH", "data/assistant.db"),
            knowledge_dir=base / os.getenv("KNOWLEDGE_DIR", "knowledge"),
            auto_reply_delay=delay,
            max_buffer_messages=int(os.getenv("MAX_BUFFER_MESSAGES", "5")),
            max_buffer_chars=int(os.getenv("MAX_BUFFER_CHARS", "3000")),
            llm_url=llm_url,
            llm_model=os.getenv("LLM_MODEL", "qwen3-0.6b"),
            llm_timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "160")),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
            allow_remote_llm=allow_remote,
            retrieval_limit=int(os.getenv("RAG_TOP_K", "3")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            admin_cli=_bool("ADMIN_CLI", True),
            spam_window_seconds=spam_window,
            spam_warn_threshold=spam_threshold,
            catalog_sheet_id=os.getenv("CATALOG_SHEET_ID", "").strip(),
            catalog_sheet_range=os.getenv("CATALOG_SHEET_RANGE", "Menu!A1:G1000"),
            catalog_credentials=base / credentials if credentials else None,
            catalog_cache_seconds=cache_seconds,
            catalog_timeout=catalog_timeout,
            catalog_csv_url=csv_url,
        )
