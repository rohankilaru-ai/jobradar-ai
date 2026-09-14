"""Fetch sources with ETag cache. Isolate per-source failures."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.parsers import parse_source
from jobradar.sources import SOURCES, Source

log = logging.getLogger("jobradar.scout")


@dataclass
class ScoutResult:
    source: str
    jobs: list[JobRecord]
    error: str | None = None
    status: int | None = None
    not_modified: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_source(source: Source, db: Database, client: httpx.Client | None = None) -> ScoutResult:
    own = client is None
    client = client or httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        etag = None
        with db.connection() as conn:
            row = conn.execute("SELECT etag FROM fetch_cache WHERE url = ?", (source.url,)).fetchone()
            if row:
                etag = row["etag"]
        headers = {"User-Agent": "JobRadar-AI/0.1 (+personal internship scout)"}
        if etag:
            headers["If-None-Match"] = etag
        resp = client.get(source.url, headers=headers)
        if resp.status_code == 304:
            return ScoutResult(source=source.name, jobs=[], status=304, not_modified=True)
        if resp.status_code >= 400:
            return ScoutResult(source=source.name, jobs=[], error=f"HTTP {resp.status_code}", status=resp.status_code)
        body = resp.text
        new_etag = resp.headers.get("ETag")
        with db.connection() as conn:
            conn.execute(
                """
                INSERT INTO fetch_cache (url, etag, body, fetched_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                  etag=excluded.etag,
                  body=excluded.body,
                  fetched_at=excluded.fetched_at
                """,
                (source.url, new_etag, "", _now()),
            )
        jobs = parse_source(source.kind, body, source.name)
        return ScoutResult(source=source.name, jobs=jobs, status=resp.status_code)
    except Exception as exc:  # isolate failures
        log.exception("scout failed for %s", source.name)
        return ScoutResult(source=source.name, jobs=[], error=str(exc))
    finally:
        if own:
            client.close()


def scout_all(db: Database, sources: list[Source] | None = None) -> list[ScoutResult]:
    sources = SOURCES if sources is None else sources
    results: list[ScoutResult] = []
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for src in sources:
            results.append(fetch_source(src, db, client=client))
    return results
