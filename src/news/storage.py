"""SQLite storage for news cache."""
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class NewsStorage:
    """SQLite cache for articles and summaries."""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        canonical_url TEXT UNIQUE NOT NULL,
        published_at_utc TEXT NOT NULL,
        fetched_at_utc TEXT NOT NULL,
        excerpt TEXT,
        fingerprint TEXT,
        created_at TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL UNIQUE,
        summary TEXT NOT NULL,
        summary_origin TEXT,
        summary_model TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_articles_canonical_url ON articles(canonical_url);
    CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at_utc);
    CREATE INDEX IF NOT EXISTS idx_summaries_created_at ON summaries(created_at);
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript(self.SCHEMA)
                conn.commit()
            logger.info("News database initialized at %s", self.db_path)
        except sqlite3.Error as e:
            logger.exception("Database initialization error")
            raise
    
    def insert_articles(self, articles: list) -> dict[str, int]:
        """Insert articles, return mapping of canonical_url -> article_id."""
        url_to_id = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                for article in articles:
                    try:
                        cursor = conn.execute(
                            """
                            INSERT INTO articles
                            (source_id, category, title, canonical_url, published_at_utc, 
                             fetched_at_utc, excerpt, fingerprint, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                article.source_id,
                                article.category,
                                article.title,
                                article.canonical_url,
                                article.published_at_utc.isoformat(),
                                article.fetched_at_utc.isoformat(),
                                article.excerpt,
                                article.fingerprint,
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                        url_to_id[article.canonical_url] = cursor.lastrowid
                    except sqlite3.IntegrityError:
                        # URL already exists, fetch its ID
                        cursor = conn.execute(
                            "SELECT id FROM articles WHERE canonical_url = ?",
                            (article.canonical_url,),
                        )
                        row = cursor.fetchone()
                        if row:
                            url_to_id[article.canonical_url] = row[0]
                
                conn.commit()
        except sqlite3.Error as e:
            logger.exception("Error inserting articles")
        
        return url_to_id
    
    def insert_summary(
        self,
        article_id: int,
        summary: str,
        summary_origin: str,
        summary_model: str,
    ) -> bool:
        """Insert or update summary for article."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO summaries
                    (article_id, summary, summary_origin, summary_model, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        article_id,
                        summary,
                        summary_origin,
                        summary_model,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
            return True
        except sqlite3.Error as e:
            logger.exception("Error inserting summary")
            return False
    
    def get_summary(self, article_id: int) -> Optional[tuple[str, str]]:
        """Get cached summary for article. Returns (summary, origin) or None."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT summary, summary_origin FROM summaries WHERE article_id = ?",
                    (article_id,),
                )
                row = cursor.fetchone()
                return row if row else None
        except sqlite3.Error as e:
            logger.exception("Error retrieving summary")
            return None
    
    def cleanup_old_records(
        self,
        article_retention_days: int = 14,
        summary_retention_days: int = 7,
    ):
        """Remove old articles and summaries."""
        try:
            now = datetime.now(timezone.utc)
            article_cutoff = (now - timedelta(days=article_retention_days)).isoformat()
            summary_cutoff = (now - timedelta(days=summary_retention_days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                # Delete old summaries
                cursor = conn.execute(
                    "DELETE FROM summaries WHERE created_at < ?",
                    (summary_cutoff,),
                )
                summary_deleted = cursor.rowcount
                
                # Delete old articles
                cursor = conn.execute(
                    "DELETE FROM articles WHERE created_at < ?",
                    (article_cutoff,),
                )
                article_deleted = cursor.rowcount
                
                conn.commit()
            
            if article_deleted > 0 or summary_deleted > 0:
                logger.info("Cleaned up %d articles and %d summaries", article_deleted, summary_deleted)
        except sqlite3.Error as e:
            logger.exception("Error cleaning up old records")
    
    def get_recent_articles(self, limit: int = 100) -> list[dict]:
        """Get recent articles from cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM articles ORDER BY fetched_at_utc DESC LIMIT ?
                    """,
                    (limit,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.exception("Error retrieving recent articles")
            return []
