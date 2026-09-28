import logging
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)
UTC = timezone.utc


class VoiceStatsStore:
    """Small SQLite store for completed and currently active voice sessions."""

    def __init__(self, database_path: str | Path, timezone_name: str = "Asia/Jakarta") -> None:
        self.path = Path(database_path)
        self.timezone = ZoneInfo(timezone_name)
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _run(self, callback):
        for attempt in range(3):
            try:
                with self._lock, self._connect() as connection:
                    return callback(connection)
            except sqlite3.OperationalError as error:
                if "locked" not in str(error).lower() or attempt == 2:
                    raise
                time.sleep(0.2 * (attempt + 1))

    def _initialize(self) -> None:
        def initialize(connection: sqlite3.Connection) -> None:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS voice_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    channel_name TEXT NOT NULL,
                    joined_at TEXT NOT NULL,
                    left_at TEXT,
                    duration_seconds INTEGER
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_voice_sessions_active "
                "ON voice_sessions(guild_id, user_id, left_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_voice_sessions_joined "
                "ON voice_sessions(joined_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS voice_exports (
                    period TEXT PRIMARY KEY,
                    exported_at TEXT NOT NULL
                )
                """
            )

        self._run(initialize)

    @staticmethod
    def _timestamp(value: datetime | None = None) -> str:
        return (value or datetime.now(UTC)).astimezone(UTC).isoformat()

    @staticmethod
    def _parse(value: str) -> datetime:
        return datetime.fromisoformat(value).astimezone(UTC)

    def start_session(
        self, guild_id: int, user_id: int, username: str, channel_id: int, channel_name: str, now: datetime | None = None
    ) -> bool:
        joined_at = self._timestamp(now)

        def start(connection: sqlite3.Connection) -> bool:
            active = connection.execute(
                "SELECT id, channel_id FROM voice_sessions WHERE guild_id = ? AND user_id = ? AND left_at IS NULL "
                "ORDER BY id DESC LIMIT 1",
                (guild_id, user_id),
            ).fetchone()
            if active and active["channel_id"] == channel_id:
                return False
            if active:
                self._close_connection(connection, active["id"], joined_at)
            connection.execute(
                "INSERT INTO voice_sessions (guild_id, user_id, username, channel_id, channel_name, joined_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (guild_id, user_id, username, channel_id, channel_name, joined_at),
            )
            return True

        return self._run(start)

    def _close_connection(self, connection: sqlite3.Connection, session_id: int, left_at: str) -> bool:
        session = connection.execute("SELECT joined_at FROM voice_sessions WHERE id = ? AND left_at IS NULL", (session_id,)).fetchone()
        if not session:
            return False
        duration = max(0, int((self._parse(left_at) - self._parse(session["joined_at"])).total_seconds()))
        connection.execute(
            "UPDATE voice_sessions SET left_at = ?, duration_seconds = ? WHERE id = ?",
            (left_at, duration, session_id),
        )
        return True

    def close_session(self, guild_id: int, user_id: int, now: datetime | None = None) -> bool:
        left_at = self._timestamp(now)

        def close(connection: sqlite3.Connection) -> bool:
            session = connection.execute(
                "SELECT id FROM voice_sessions WHERE guild_id = ? AND user_id = ? AND left_at IS NULL "
                "ORDER BY id DESC LIMIT 1",
                (guild_id, user_id),
            ).fetchone()
            return bool(session and self._close_connection(connection, session["id"], left_at))

        return self._run(close)

    def active_sessions(self, guild_id: int | None = None) -> list[sqlite3.Row]:
        def get_active(connection: sqlite3.Connection):
            query = "SELECT * FROM voice_sessions WHERE left_at IS NULL"
            params: tuple = ()
            if guild_id is not None:
                query += " AND guild_id = ?"
                params = (guild_id,)
            return connection.execute(query, params).fetchall()

        return self._run(get_active)

    def sessions_overlapping(self, start: datetime, end: datetime) -> list[sqlite3.Row]:
        start_value, end_value = self._timestamp(start), self._timestamp(end)

        def get_sessions(connection: sqlite3.Connection):
            return connection.execute(
                "SELECT * FROM voice_sessions WHERE joined_at < ? AND (left_at IS NULL OR left_at > ?) ORDER BY joined_at",
                (end_value, start_value),
            ).fetchall()

        return self._run(get_sessions)

    def summarize(self, start: datetime, end: datetime) -> dict:
        now = datetime.now(UTC)
        rows = self.sessions_overlapping(start, end)
        members: dict[str, int] = defaultdict(int)
        channels: dict[str, int] = defaultdict(int)
        daily: dict[str, dict] = {}
        total = 0
        session_count = 0
        active_users: set[int] = set()

        for row in rows:
            row_start = self._parse(row["joined_at"])
            row_end = self._parse(row["left_at"]) if row["left_at"] else now
            overlap_start, overlap_end = max(row_start, start), min(row_end, end)
            if overlap_end <= overlap_start:
                continue
            session_count += 1
            active_users.add(row["user_id"])
            seconds = int((overlap_end - overlap_start).total_seconds())
            total += seconds
            members[row["username"]] += seconds
            channels[row["channel_name"]] += seconds
            cursor = overlap_start
            while cursor < overlap_end:
                local_cursor = cursor.astimezone(self.timezone)
                next_day = datetime.combine(local_cursor.date() + timedelta(days=1), datetime.min.time(), self.timezone).astimezone(UTC)
                segment_end = min(overlap_end, next_day)
                date_key = local_cursor.date().isoformat()
                entry = daily.setdefault(date_key, {"seconds": 0, "members": set(), "sessions": set()})
                entry["seconds"] += int((segment_end - cursor).total_seconds())
                entry["members"].add(row["user_id"])
                entry["sessions"].add(row["id"])
                cursor = segment_end

        return {
            "total_seconds": total,
            "sessions": session_count,
            "active_members": len(active_users),
            "members": dict(sorted(members.items(), key=lambda item: item[1], reverse=True)),
            "channels": dict(sorted(channels.items(), key=lambda item: item[1], reverse=True)),
            "daily": daily,
            "rows": rows,
        }

    def mark_exported(self, period: str) -> None:
        exported_at = self._timestamp()
        self._run(lambda connection: connection.execute(
            "INSERT INTO voice_exports(period, exported_at) VALUES (?, ?) "
            "ON CONFLICT(period) DO UPDATE SET exported_at = excluded.exported_at",
            (period, exported_at),
        ))

    def was_exported(self, period: str) -> bool:
        return bool(self._run(lambda connection: connection.execute(
            "SELECT 1 FROM voice_exports WHERE period = ?", (period,)
        ).fetchone()))

    def count_period(self, start: datetime, end: datetime) -> int:
        return len(self.sessions_overlapping(start, end))

    def delete_period(self, start: datetime, end: datetime) -> int:
        start_value, end_value = self._timestamp(start), self._timestamp(end)

        def delete(connection: sqlite3.Connection) -> int:
            rows = connection.execute(
                "SELECT * FROM voice_sessions WHERE joined_at < ? AND (left_at IS NULL OR left_at > ?)",
                (end_value, start_value),
            ).fetchall()
            for row in rows:
                starts_before = row["joined_at"] < start_value
                ends_after = row["left_at"] is None or row["left_at"] > end_value
                if starts_before and ends_after:
                    # Preserve both portions outside the deleted period as two sessions.
                    duration_before = max(0, int((self._parse(start_value) - self._parse(row["joined_at"])).total_seconds()))
                    connection.execute(
                        "UPDATE voice_sessions SET left_at = ?, duration_seconds = ? WHERE id = ?",
                        (start_value, duration_before, row["id"]),
                    )
                    connection.execute(
                        "INSERT INTO voice_sessions (guild_id, user_id, username, channel_id, channel_name, joined_at, left_at, duration_seconds) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (row["guild_id"], row["user_id"], row["username"], row["channel_id"], row["channel_name"],
                         end_value, row["left_at"],
                         None if row["left_at"] is None else max(0, int((self._parse(row["left_at"]) - self._parse(end_value)).total_seconds()))),
                    )
                elif starts_before:
                    duration_before = max(0, int((self._parse(start_value) - self._parse(row["joined_at"])).total_seconds()))
                    connection.execute(
                        "UPDATE voice_sessions SET left_at = ?, duration_seconds = ? WHERE id = ?",
                        (start_value, duration_before, row["id"]),
                    )
                elif ends_after:
                    connection.execute(
                        "UPDATE voice_sessions SET joined_at = ?, duration_seconds = NULL WHERE id = ?",
                        (end_value, row["id"]),
                    )
                else:
                    connection.execute("DELETE FROM voice_sessions WHERE id = ?", (row["id"],))
            return len(rows)

        return self._run(delete)

    def vacuum(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("VACUUM")

    def storage_info(self) -> dict:
        def info(connection: sqlite3.Connection) -> dict:
            row = connection.execute(
                "SELECT COUNT(*) AS sessions, MIN(joined_at) AS oldest, MAX(COALESCE(left_at, joined_at)) AS newest FROM voice_sessions"
            ).fetchone()
            return dict(row)

        result = self._run(info)
        result["size_bytes"] = self.path.stat().st_size if self.path.exists() else 0
        return result
