"""Notifiers — mock JSONL until Twilio/Discord keys exist."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from jobradar.db import Database
from jobradar.models import JobRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_alert(job: JobRecord) -> str:
    prefix = "[PRIORITY] " if job.priority else ""
    source = job.sources[0] if job.sources else "unknown"
    summary = job.snippet or f"{job.title} at {job.company}"
    # two-line summary preference
    lines = summary.strip().splitlines()
    if len(lines) == 1:
        summary_block = lines[0]
    else:
        summary_block = "\n".join(lines[:2])
    return (
        f"{prefix}{job.company}\n"
        f"{job.title} | {job.location}\n"
        f"{source} | {job.url}\n\n"
        f"{summary_block}"
    )


class MockNotifier:
    def __init__(self, path: Path | str | None = None, db: Database | None = None) -> None:
        self.path = Path(path or os.environ.get("JOBRADAR_NOTIFY_MOCK_PATH", "data/notifications.jsonl"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = db

    def notify(self, job: JobRecord) -> bool:
        """Return True if newly notified, False if already notified."""
        if self.db and self.db.was_notified(job.canonical_key):
            return False
        payload = format_alert(job)
        record = {
            "ts": _now(),
            "channel": "mock",
            "canonical_key": job.canonical_key,
            "priority": job.priority,
            "text": payload,
            "job": job.webhook_payload()["job"],
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if self.db:
            self.db.record_notification(job.canonical_key, "mock", payload, record["ts"])
        return True
