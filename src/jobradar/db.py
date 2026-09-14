"""SQLite persistence for JobRadar."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from jobradar.models import JobRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  canonical_key TEXT PRIMARY KEY,
  company TEXT NOT NULL,
  title TEXT NOT NULL,
  location TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  sources_json TEXT NOT NULL DEFAULT '[]',
  snippet TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 0,
  season TEXT NOT NULL DEFAULT '',
  is_closed INTEGER NOT NULL DEFAULT 0,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT NOT NULL,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  UNIQUE(canonical_key, source)
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT NOT NULL UNIQUE,
  channel TEXT NOT NULL,
  payload TEXT NOT NULL,
  sent_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent TEXT NOT NULL,
  canonical_key TEXT,
  status TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fetch_cache (
  url TEXT PRIMARY KEY,
  etag TEXT,
  body TEXT,
  fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emails (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id TEXT UNIQUE,
  subject TEXT,
  classification TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT,
  status TEXT,
  created_at TEXT
);
"""


def default_db_path() -> Path:
    env = os.environ.get("JOBRADAR_DB_PATH", "data/jobradar.db")
    return Path(env)


class Database:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_db_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert_job(self, job: JobRecord) -> tuple[JobRecord, bool]:
        """Insert or merge job. Returns (job, is_new)."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE canonical_key = ?",
                (job.canonical_key,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO jobs (
                      canonical_key, company, title, location, url, sources_json,
                      snippet, priority, season, is_closed, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.canonical_key,
                        job.company,
                        job.title,
                        job.location,
                        job.url,
                        json.dumps(job.sources),
                        job.snippet,
                        1 if job.priority else 0,
                        job.season,
                        1 if job.is_closed else 0,
                        job.first_seen_at,
                        job.last_seen_at,
                    ),
                )
                for src in job.sources:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO job_sources (canonical_key, source, fetched_at)
                        VALUES (?, ?, ?)
                        """,
                        (job.canonical_key, src, job.last_seen_at),
                    )
                return job, True

            existing_sources = json.loads(row["sources_json"] or "[]")
            merged_sources = list(dict.fromkeys([*existing_sources, *job.sources]))
            conn.execute(
                """
                UPDATE jobs SET
                  company = ?,
                  title = ?,
                  location = COALESCE(NULLIF(?, ''), location),
                  url = COALESCE(NULLIF(?, ''), url),
                  sources_json = ?,
                  snippet = COALESCE(NULLIF(?, ''), snippet),
                  priority = MAX(priority, ?),
                  season = COALESCE(NULLIF(?, ''), season),
                  is_closed = MAX(is_closed, ?),
                  last_seen_at = ?
                WHERE canonical_key = ?
                """,
                (
                    job.company or row["company"],
                    job.title or row["title"],
                    job.location,
                    job.url,
                    json.dumps(merged_sources),
                    job.snippet,
                    1 if job.priority else 0,
                    job.season,
                    1 if job.is_closed else 0,
                    job.last_seen_at,
                    job.canonical_key,
                ),
            )
            for src in job.sources:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO job_sources (canonical_key, source, fetched_at)
                    VALUES (?, ?, ?)
                    """,
                    (job.canonical_key, src, job.last_seen_at),
                )
            updated = self.get_job(job.canonical_key, conn=conn)
            assert updated is not None
            return updated, False

    def get_job(self, key: str, conn: sqlite3.Connection | None = None) -> JobRecord | None:
        def _load(c: sqlite3.Connection) -> JobRecord | None:
            row = c.execute("SELECT * FROM jobs WHERE canonical_key = ?", (key,)).fetchone()
            if row is None:
                return None
            return JobRecord(
                company=row["company"],
                title=row["title"],
                location=row["location"],
                url=row["url"],
                sources=json.loads(row["sources_json"] or "[]"),
                snippet=row["snippet"],
                priority=bool(row["priority"]),
                season=row["season"],
                is_closed=bool(row["is_closed"]),
                first_seen_at=row["first_seen_at"],
                last_seen_at=row["last_seen_at"],
                canonical_key=row["canonical_key"],
            )

        if conn is not None:
            return _load(conn)
        with self.connection() as c:
            return _load(c)

    def was_notified(self, key: str) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM notifications WHERE canonical_key = ?",
                (key,),
            ).fetchone()
            return row is not None

    def record_notification(self, key: str, channel: str, payload: str, sent_at: str) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO notifications (canonical_key, channel, payload, sent_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, channel, payload, sent_at),
            )

    def count_jobs(self) -> int:
        with self.connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
