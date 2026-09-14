"""Notion Applications database. Skip if token/id missing."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from jobradar.db import Database
from jobradar.models import JobRecord

log = logging.getLogger("jobradar.notion")

STATUS_SEEN = "Seen"


def configured() -> bool:
    return bool((os.environ.get("NOTION_TOKEN") or "").strip()) and bool(
        (os.environ.get("NOTION_DATABASE_ID") or "").strip()
    )


def _client():
    from notion_client import Client

    return Client(auth=os.environ["NOTION_TOKEN"].strip())


def _db_id() -> str:
    return os.environ["NOTION_DATABASE_ID"].strip().replace("-", "")


def _date_prop(iso: str) -> dict:
    day = (iso or "")[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {"date": {"start": day}}


def page_properties(job: JobRecord, status: str = STATUS_SEEN, gmail_thread: str = "") -> dict:
    source = job.sources[0] if job.sources else ""
    props: dict = {
        "Name": {"title": [{"text": {"content": f"{job.company} — {job.title}"[:100]}}]},
        "Company": {"rich_text": [{"text": {"content": (job.company or "")[:200]}}]},
        "Role": {"rich_text": [{"text": {"content": (job.title or "")[:200]}}]},
        "Location": {"rich_text": [{"text": {"content": (job.location or "")[:200]}}]},
        "Status": {"select": {"name": status}},
        "Priority": {"checkbox": bool(job.priority)},
        "Source": {"rich_text": [{"text": {"content": source[:200]}}]},
        "Canonical key": {"rich_text": [{"text": {"content": job.canonical_key[:200]}}]},
        "First seen": _date_prop(job.first_seen_at),
        "Last update": _date_prop(job.last_seen_at),
    }
    if job.url:
        props["URL"] = {"url": job.url}
    if gmail_thread:
        props["Gmail thread"] = {"url": gmail_thread}
    return props


def find_page_id(canonical_key: str) -> str | None:
    if not configured():
        return None
    notion = _client()
    result = notion.databases.query(
        database_id=_db_id(),
        filter={
            "property": "Canonical key",
            "rich_text": {"equals": canonical_key},
        },
        page_size=1,
    )
    results = result.get("results") or []
    if not results:
        return None
    return results[0]["id"]


def upsert_job(
    job: JobRecord,
    db: Database | None = None,
    *,
    status: str = STATUS_SEEN,
    gmail_thread: str = "",
) -> str | None:
    if not configured():
        return None
    notion = _client()
    props = page_properties(job, status=status, gmail_thread=gmail_thread)
    existing = None
    if db:
        app = db.get_application(job.canonical_key)
        if app and app.get("notion_page_id"):
            existing = app["notion_page_id"]
    if not existing:
        try:
            existing = find_page_id(job.canonical_key)
        except Exception as exc:
            log.warning("notion query failed: %s", exc)
    try:
        if existing:
            notion.pages.update(page_id=existing, properties=props)
            page_id = existing
        else:
            created = notion.pages.create(parent={"database_id": _db_id()}, properties=props)
            page_id = created["id"]
    except Exception as exc:
        log.warning("notion upsert failed: %s", exc)
        return None
    if db:
        db.upsert_application(
            canonical_key=job.canonical_key,
            company=job.company,
            title=job.title,
            status=status,
            notion_page_id=page_id,
            gmail_thread_id=gmail_thread or None,
        )
    return page_id


def test_connection() -> str:
    if not configured():
        return "skipped (no NOTION_TOKEN / NOTION_DATABASE_ID)"
    notion = _client()
    notion.databases.retrieve(database_id=_db_id())
    return "ok"


def backfill(db: Database, *, priority_only: bool = True, limit: int | None = None) -> int:
    n = 0
    for job in db.list_jobs(priority_only=priority_only, limit=limit):
        if upsert_job(job, db=db):
            n += 1
    return n
