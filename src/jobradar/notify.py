"""Notifiers — JSONL always; Discord / ntfy / Telegram if env is set.

Phone push is free via ntfy.sh (no Twilio). Failures never abort the scan.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from jobradar.db import Database
from jobradar.models import JobRecord

log = logging.getLogger("jobradar.notify")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_alert(job: JobRecord) -> str:
    prefix = "[PRIORITY] " if job.priority else ""
    source = job.sources[0] if job.sources else "unknown"
    summary = job.snippet or f"{job.title} at {job.company}"
    lines = summary.strip().splitlines()
    summary_block = lines[0] if len(lines) == 1 else "\n".join(lines[:2])
    return (
        f"{prefix}{job.company}\n"
        f"{job.title} | {job.location}\n"
        f"{source} | {job.url}\n\n"
        f"{summary_block}"
    )


def discord_configured() -> bool:
    return bool((os.environ.get("DISCORD_WEBHOOK_URL") or "").strip())


def ntfy_configured() -> bool:
    return bool((os.environ.get("NTFY_TOPIC") or "").strip())


def telegram_configured() -> bool:
    return bool((os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()) and bool(
        (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    )


def send_discord(text: str) -> str:
    url = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    if not url:
        return "skipped"
    resp = httpx.post(url, json={"content": text[:1900]}, timeout=8.0)
    if resp.status_code >= 400:
        raise RuntimeError(f"discord HTTP {resp.status_code}")
    return "ok"


def send_ntfy(text: str, *, priority: bool = False, title: str = "JobRadar") -> str:
    """Free phone push via ntfy.sh (or self-hosted NTFY_SERVER)."""
    topic = (os.environ.get("NTFY_TOPIC") or "").strip()
    if not topic:
        return "skipped"
    server = (os.environ.get("NTFY_SERVER") or "https://ntfy.sh").strip().rstrip("/")
    url = f"{server}/{quote(topic, safe='')}"
    headers = {
        "Title": title[:200],
        "Priority": "5" if priority else "3",
        "Tags": "briefcase",
    }
    token = (os.environ.get("NTFY_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = httpx.post(url, content=text[:4000].encode("utf-8"), headers=headers, timeout=8.0)
    if resp.status_code >= 400:
        raise RuntimeError(f"ntfy HTTP {resp.status_code}: {resp.text[:200]}")
    return "ok"


def send_telegram(text: str) -> str:
    """Free Telegram bot message (unlimited enough for personal internship alerts)."""
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        return "skipped"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = httpx.post(
        url,
        json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": False},
        timeout=8.0,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"telegram HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"telegram error: {data}")
    return "ok"


class Notifier:
    def __init__(self, path: Path | str | None = None, db: Database | None = None) -> None:
        self.path = Path(path or os.environ.get("JOBRADAR_NOTIFY_MOCK_PATH", "data/notifications.jsonl"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = db

    def notify(self, job: JobRecord) -> bool:
        if self.db and self.db.was_notified(job.canonical_key):
            return False
        payload = format_alert(job)
        record = {
            "ts": _now(),
            "channel": "jsonl",
            "canonical_key": job.canonical_key,
            "priority": job.priority,
            "text": payload,
            "job": job.webhook_payload()["job"],
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if self.db:
            self.db.record_notification(job.canonical_key, "jsonl", payload, record["ts"])
        try:
            send_discord(payload)
        except Exception as exc:
            log.warning("discord webhook failed: %s", exc)
        try:
            send_ntfy(payload, priority=bool(job.priority), title=f"{job.company} — {job.title}"[:80])
        except Exception as exc:
            log.warning("ntfy push failed: %s", exc)
        try:
            send_telegram(payload)
        except Exception as exc:
            log.warning("telegram failed: %s", exc)
        return True


# Back-compat name used by existing tests
MockNotifier = Notifier
