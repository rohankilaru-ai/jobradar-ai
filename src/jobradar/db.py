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
  thread_id TEXT,
  subject TEXT,
  from_addr TEXT,
  classification TEXT,
  canonical_key TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT UNIQUE,
  company TEXT,
  title TEXT,
  status TEXT,
  date_applied TEXT,
  last_update TEXT,
  gmail_thread_id TEXT,
  notion_page_id TEXT,
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
            self._migrate(conn)
            conn.commit()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        def cols(table: str) -> set[str]:
            return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}

        app = cols("applications")
        for name, typ in (
            ("company", "TEXT"),
            ("title", "TEXT"),
            ("date_applied", "TEXT"),
            ("last_update", "TEXT"),
            ("gmail_thread_id", "TEXT"),
            ("notion_page_id", "TEXT"),
        ):
            if name not in app:
                conn.execute(f"ALTER TABLE applications ADD COLUMN {name} {typ}")
        em = cols("emails")
        for name, typ in (
            ("thread_id", "TEXT"),
            ("from_addr", "TEXT"),
            ("canonical_key", "TEXT"),
        ):
            if name not in em:
                conn.execute(f"ALTER TABLE emails ADD COLUMN {name} {typ}")

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

    def record_agent_run(self, agent: str, key: str | None, status: str, detail: str = "") -> None:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs (agent, canonical_key, status, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (agent, key, status, detail, ts),
            )

    def list_jobs(self, *, priority_only: bool = False, limit: int | None = None) -> list[JobRecord]:
        sql = "SELECT canonical_key FROM jobs"
        params: list = []
        if priority_only:
            sql += " WHERE priority = 1"
        sql += " ORDER BY last_seen_at DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as conn:
            keys = [r[0] for r in conn.execute(sql, params)]
        out: list[JobRecord] = []
        for key in keys:
            job = self.get_job(key)
            if job:
                out.append(job)
        return out

    def upsert_application(
        self,
        *,
        canonical_key: str,
        company: str = "",
        title: str = "",
        status: str = "Seen",
        date_applied: str | None = None,
        gmail_thread_id: str | None = None,
        notion_page_id: str | None = None,
    ) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM applications WHERE canonical_key = ?",
                (canonical_key,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO applications (
                      canonical_key, company, title, status, date_applied,
                      last_update, gmail_thread_id, notion_page_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_key,
                        company,
                        title,
                        status,
                        date_applied,
                        now,
                        gmail_thread_id,
                        notion_page_id,
                        now,
                    ),
                )
                return
            conn.execute(
                """
                UPDATE applications SET
                  company = COALESCE(NULLIF(?, ''), company),
                  title = COALESCE(NULLIF(?, ''), title),
                  status = COALESCE(NULLIF(?, ''), status),
                  date_applied = COALESCE(?, date_applied),
                  last_update = ?,
                  gmail_thread_id = COALESCE(?, gmail_thread_id),
                  notion_page_id = COALESCE(?, notion_page_id)
                WHERE canonical_key = ?
                """,
                (
                    company,
                    title,
                    status,
                    date_applied,
                    now,
                    gmail_thread_id,
                    notion_page_id,
                    canonical_key,
                ),
            )

    def get_application(self, canonical_key: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM applications WHERE canonical_key = ?",
                (canonical_key,),
            ).fetchone()
            return dict(row) if row else None

    def find_job_by_company(self, company: str) -> JobRecord | None:
        needle = (company or "").strip().lower()
        if len(needle) < 3:
            return None
        with self.connection() as conn:
            rows = conn.execute("SELECT canonical_key, company FROM jobs").fetchall()
        for row in rows:
            name = (row["company"] or "").lower()
            if needle in name or name in needle:
                return self.get_job(row["canonical_key"])
        return None

    def record_email(
        self,
        *,
        message_id: str,
        thread_id: str = "",
        subject: str = "",
        from_addr: str = "",
        classification: str = "",
        canonical_key: str | None = None,
    ) -> bool:
        """Insert email. Returns False if already seen."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO emails (
                      message_id, thread_id, subject, from_addr,
                      classification, canonical_key, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (message_id, thread_id, subject, from_addr, classification, canonical_key, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def count_applications(self) -> int:
        with self.connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0])
