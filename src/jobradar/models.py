"""Core JobRecord model and helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Placeholder/invalid URL patterns to reject
_BAD_URL_PATTERNS = {
    "example.com",
    "example.org",
    "example.net",
    "test.com",
    "test.org",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "about:blank",
}


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = _WS.sub(" ", s)
    return s


def _is_generic_career_page(url: str) -> bool:
    """
    Check if URL is a generic career search/listing page (not a specific job posting).
    Used at ingest to filter out aggregator and search pages.
    """
    if not url:
        return False
    
    url = url.strip()
    if not url.startswith("http"):
        return False
    
    url_lower = url.lower()
    parsed = urlparse(url_lower)
    domain = parsed.netloc.lstrip("www.")
    path = parsed.path.rstrip("/")
    query = parsed.query
    
    # Block: dreamworkhq.com is an aggregator
    if "dreamworkhq.com" in domain:
        return True
    
    # Block: Generic career search patterns
    generic_patterns = [
        "/careers/search", "/jobs/search",
        "/careers/results", "/jobs/results",
        "/careers/openings", "/jobs/openings",
        "/job-search", "/job-listings",
    ]
    if any(pattern in path for pattern in generic_patterns):
        return True
    
    # Block: Career homepage without job identifier (exact match only)
    # This catches /careers or /jobs at the end of the path, not as part of a longer path
    if path in ["/careers", "/jobs", "/career", "/job"]:
        return True
    
    # Block: Query-based searches
    if query and any(param in query for param in ("query=", "search=", "q=", "keyword=")):
        # Unless it has a job identifier
        if not any(param in query for param in ("gh_jid=", "job_id=", "jobid=", "id=")):
            return True
    
    return False


def is_bad_url(url: str) -> bool:
    """Check if URL is empty, whitespace-only, or a known placeholder."""
    url = (url or "").strip()
    if not url:
        return True
    if url.lower().startswith(("javascript:", "mailto:", "data:", "#")):
        return True
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return True
        netloc_lower = parsed.netloc.lower()
        for bad in _BAD_URL_PATTERNS:
            if bad in netloc_lower:
                return True
        # Check if it's a generic career page (not a specific job)
        if _is_generic_career_page(url):
            return True
    except Exception:
        return True
    return False


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
