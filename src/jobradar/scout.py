"""Fetch sources with ETag cache. Isolate per-source failures."""

from __future__ import annotations

import logging
import time
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


def _is_transient_error(exc: Exception | None, status: int | None) -> bool:
    """Check if error is transient (should retry) vs hard failure (skip retry)."""
    # HTTP status-based transient detection
    if status is not None:
        if status == 429:  # Rate limit
            return True
        if 500 <= status < 600:  # Server errors
            return True
        return False  # 4xx (except 429) are hard failures
    
    # Exception-based transient detection
    if exc is not None:
        # httpx timeout and connection errors are transient
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout)):
            return True
    
    return False


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
        
        # Retry loop: try once, retry on transient failure, fail on second attempt or hard failure
        last_exc = None
        last_status = None
        for attempt in range(2):  # 0 = first attempt, 1 = retry
            try:
                resp = client.get(source.url, headers=headers)
                
                # Success cases
                if resp.status_code == 304:
                    return ScoutResult(source=source.name, jobs=[], status=304, not_modified=True)
                if resp.status_code < 400:
                    # 2xx/3xx success - parse and store
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
                
                # 4xx/5xx failure
                last_status = resp.status_code
                last_exc = None
                
                # Check if transient (429, 5xx) or hard failure (other 4xx)
                if not _is_transient_error(None, resp.status_code):
                    # Hard failure (4xx except 429) - don't retry
                    return ScoutResult(source=source.name, jobs=[], error=f"HTTP {resp.status_code}", status=resp.status_code)
                
                # Transient failure - retry if first attempt
                if attempt == 0:
                    log.warning("scout transient HTTP %d for %s, retrying...", resp.status_code, source.name)
                    time.sleep(1.0)  # Small backoff for CI
                    continue
                
                # Second attempt failed
                return ScoutResult(source=source.name, jobs=[], error=f"HTTP {resp.status_code}", status=resp.status_code)
                
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout) as exc:
                # Transient network failure
                last_exc = exc
                last_status = None
                
                if attempt == 0:
                    log.warning("scout transient error for %s: %s, retrying...", source.name, type(exc).__name__)
                    time.sleep(1.0)  # Small backoff for CI
                    continue
                
                # Second attempt failed
                log.exception("scout failed for %s after retry", source.name)
                return ScoutResult(source=source.name, jobs=[], error=str(exc))
        
        # Should not reach here, but handle gracefully
        if last_status is not None:
            return ScoutResult(source=source.name, jobs=[], error=f"HTTP {last_status}", status=last_status)
        if last_exc is not None:
            return ScoutResult(source=source.name, jobs=[], error=str(last_exc))
        return ScoutResult(source=source.name, jobs=[], error="Unknown error after retry")
        
    except Exception as exc:  # Other exceptions (non-transient)
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
