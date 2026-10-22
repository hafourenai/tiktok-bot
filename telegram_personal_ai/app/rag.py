from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .storage import Storage, now


class RagEngine:
    def __init__(self, storage: Storage, knowledge_dir: Path):
        self.storage = storage
        self.knowledge_dir = knowledge_dir

    @staticmethod
    def _chunks(text: str, size: int = 700, overlap: int = 100) -> list[str]:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        chunks, start = [], 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):
                boundary = text.rfind(". ", start, end)
                if boundary > start + size // 2:
                    end = boundary + 1
            chunks.append(text[start:end].strip())
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
        return chunks

    def reindex(self) -> int:
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        records: list[tuple[str, str, str, str]] = []
        for path in sorted(self.knowledge_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
                source = path.relative_to(self.knowledge_dir).as_posix()
                for chunk in self._chunks(path.read_text(encoding="utf-8")):
                    digest = hashlib.sha256(f"{source}\0{chunk}".encode()).hexdigest()
                    records.append((source, chunk, digest, now()))
        with self.storage._lock, self.storage._db:
            self.storage._db.execute("DELETE FROM knowledge_fts")
            self.storage._db.execute("DELETE FROM knowledge_chunks")
            self.storage._db.executemany(
                "INSERT INTO knowledge_chunks(source,content,content_hash,updated_at) VALUES(?,?,?,?)",
                records,
            )
            self.storage._db.execute(
                "INSERT INTO knowledge_fts(content,source,chunk_id) SELECT content,source,chunk_id FROM knowledge_chunks"
            )
        return len(records)

    def search(self, query: str, limit: int = 3) -> list[dict[str, str]]:
        words = re.findall(r"(?u)\b[\w-]{3,}\b", query.lower())[:12]
        if not words:
            return []
        expression = " OR ".join(f'"{word.replace(chr(34), "")}"' for word in words)
        with self.storage._lock:
            rows = self.storage._db.execute(
                "SELECT source,content,bm25(knowledge_fts) score FROM knowledge_fts "
                "WHERE knowledge_fts MATCH ? ORDER BY score LIMIT ?",
                (expression, limit),
            ).fetchall()
        return [{"source": row[0], "content": row[1]} for row in rows]
