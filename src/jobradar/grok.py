"""Best-effort Grok Bot webhook client. Empty env → skip. Never raise into notify path."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from jobradar.models import JobRecord

log = logging.getLogger("jobradar.grok")

WEBHOOK_ENV = (
    ("director", "GROK_BOT_WEBHOOK_DIRECTOR", "GROK_BOT_KEY_DIRECTOR"),
    ("job_analyst", "GROK_BOT_WEBHOOK_JOB_ANALYST", "GROK_BOT_KEY_JOB_ANALYST"),
    ("resume_mapper", "GROK_BOT_WEBHOOK_RESUME_MAPPER", "GROK_BOT_KEY_RESUME_MAPPER"),
    ("strategist", "GROK_BOT_WEBHOOK_STRATEGIST", "GROK_BOT_KEY_STRATEGIST"),
    ("inbox", "GROK_BOT_WEBHOOK_INBOX", "GROK_BOT_KEY_INBOX"),
    ("weekly", "GROK_BOT_WEBHOOK_WEEKLY", "GROK_BOT_KEY_WEEKLY"),
)


def configured_targets() -> list[str]:
    out = []
    for name, url_k, key_k in WEBHOOK_ENV:
        if os.environ.get(url_k) and os.environ.get(key_k):
            out.append(name)
    return out


def post_job(job: JobRecord, action: str = "analyze", timeout: float = 8.0) -> dict[str, Any]:
    payload = job.webhook_payload(action=action)
    results: dict[str, Any] = {}
    for name, url_k, key_k in WEBHOOK_ENV:
        url = (os.environ.get(url_k) or "").strip()
        key = (os.environ.get(key_k) or "").strip()
        if not url or not key:
            results[name] = "skipped"
            continue
        try:
            resp = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            results[name] = f"http_{resp.status_code}"
        except Exception as exc:
            log.warning("grok webhook %s failed: %s", name, exc)
            results[name] = f"error:{exc}"
    return results


def ping_all(timeout: float = 8.0) -> dict[str, Any]:
    ping = {
        "action": "ping",
        "event": "jobradar.new_job",
        "source": "jobradar-director",
        "job": {
            "company": "TestCo",
            "title": "Software Engineer Intern",
            "location": "SF",
            "url": "https://example.com",
            "sources": ["ping"],
            "snippet": "test",
            "priority": False,
        },
    }
    results: dict[str, Any] = {}
    for name, url_k, key_k in WEBHOOK_ENV:
        url = (os.environ.get(url_k) or "").strip()
        key = (os.environ.get(key_k) or "").strip()
        if not url or not key:
            results[name] = "skipped"
            continue
        try:
            resp = httpx.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=ping,
                timeout=timeout,
            )
            results[name] = f"http_{resp.status_code}"
        except Exception as exc:
            results[name] = f"error:{exc}"
    return results
