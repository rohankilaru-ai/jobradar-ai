"""Core JobRecord model and helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = _WS.sub(" ", s)
    return s


def canonical_key(company: str, title: str, location: str, url: str = "") -> str:
    """Stable unique key. Prefer URL hash when present; else company|title|location."""
    url_n = (url or "").strip()
    if url_n:
        digest = hashlib.sha256(url_n.encode("utf-8")).hexdigest()[:16]
        return f"url:{digest}"
    parts = [
        _NON_ALNUM.sub("-", _norm(company)).strip("-"),
        _NON_ALNUM.sub("-", _norm(title)).strip("-"),
        _NON_ALNUM.sub("-", _norm(location)).strip("-"),
    ]
    return "|".join(parts)


@dataclass
class JobRecord:
    company: str
    title: str
    location: str = ""
    url: str = ""
    sources: list[str] = field(default_factory=list)
    snippet: str = ""
    priority: bool = False
    season: str = ""
    is_closed: bool = False
    first_seen_at: str = ""
    last_seen_at: str = ""
    canonical_key: str = ""

    def __post_init__(self) -> None:
        if not self.canonical_key:
            self.canonical_key = canonical_key(self.company, self.title, self.location, self.url)
        now = datetime.now(timezone.utc).isoformat()
        if not self.first_seen_at:
            self.first_seen_at = now
        if not self.last_seen_at:
            self.last_seen_at = now
        if self.snippet and len(self.snippet) > 500:
            self.snippet = self.snippet[:500]
        if isinstance(self.sources, str):
            self.sources = [self.sources]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def webhook_payload(self, action: str = "analyze", source: str = "jobradar-director") -> dict[str, Any]:
        return {
            "event": "jobradar.new_job",
            "action": action,
            "source": source,
            "job": {
                "company": self.company,
                "title": self.title,
                "location": self.location,
                "url": self.url,
                "sources": list(self.sources),
                "snippet": self.snippet[:500] if self.snippet else "",
                "priority": bool(self.priority),
            },
        }
