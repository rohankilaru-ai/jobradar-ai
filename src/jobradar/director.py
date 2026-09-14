"""Wake Grok Bots after notify. Never raise into the scan path."""

from __future__ import annotations

import logging
import os

import httpx

from jobradar.db import Database
from jobradar.models import JobRecord

log = logging.getLogger("jobradar.director")

AGENT_ENV = {
    "job-analyst": ("GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_KEY_JOB_ANALYST"),
    "resume-mapper": ("GROK_BOT_WEBHOOK_RESUME_MAPPER", "GROK_BOT_KEY_RESUME_MAPPER"),
}


def _post(url: str, key: str, payload: dict) -> str:
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "JobRadar-AI/0.1",
    }
    resp = httpx.post(url, headers=headers, json=payload, timeout=8.0)
    body = {}
    try:
        body = resp.json()
    except Exception:
        body = {}
    run = body.get("runUuid") if isinstance(body, dict) else None
    if resp.status_code >= 400:
        raise RuntimeError(f"webhook {resp.status_code}")
    return str(run or "started")


def enqueue(job: JobRecord, db: Database | None = None) -> list[str]:
    """Fire-and-forget specialist wakes. Returns agent names attempted."""
    attempted: list[str] = []
    for agent, (url_var, key_var) in AGENT_ENV.items():
        url = (os.environ.get(url_var) or "").strip()
        key = (os.environ.get(key_var) or "").strip()
        if not url or not key:
            if db:
                db.record_agent_run(agent, job.canonical_key, "skipped", "missing webhook env")
            continue
        attempted.append(agent)
        try:
            run_id = _post(url, key, job.webhook_payload())
            if db:
                db.record_agent_run(agent, job.canonical_key, "queued", run_id)
        except Exception as exc:
            log.warning("director %s failed: %s", agent, exc)
            if db:
                db.record_agent_run(agent, job.canonical_key, "error", str(exc)[:300])
    return attempted


def ping_configured() -> list[str]:
    """Return status lines for CLI. Missing keys are OK."""
    lines: list[str] = []
    ping_job = JobRecord(
        company="TestCo",
        title="Software Engineer Intern",
        location="SF",
        url="https://example.com/ping",
        sources=["ping"],
        snippet="ping",
    )
    for agent, (url_var, key_var) in AGENT_ENV.items():
        url = (os.environ.get(url_var) or "").strip()
        key = (os.environ.get(key_var) or "").strip()
        if not url or not key:
            lines.append(f"{agent}: skipped (no env)")
            continue
        try:
            run_id = _post(url, key, ping_job.webhook_payload(action="ping"))
            lines.append(f"{agent}: ok runUuid={run_id}")
        except Exception as exc:
            lines.append(f"{agent}: error {exc}")
    if not lines:
        lines.append("no grok agents configured")
    return lines
