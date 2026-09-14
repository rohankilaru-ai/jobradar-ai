"""Notifiers — JSONL always; Discord / ntfy / Telegram if env is set.

Phone push is free via ntfy.sh (no Twilio). Failures never abort the scan.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from jobradar.db import Database
from jobradar.models import JobRecord

log = logging.getLogger("jobradar.notify")

# HTML tag pattern
_HTML_TAG = re.compile(r"<[^>]+>")

# Recruiting platform hosts (allowlist for domain mismatch check)
RECRUITING_HOSTS = {
    "greenhouse.io", "boards.greenhouse.io",
    "lever.co", "jobs.lever.co",
    "ashbyhq.com", "jobs.ashbyhq.com",
    "workday.com", "myworkday.com", "myworkdayjobs.com",
    "jobvite.com", "jobs.jobvite.com",
    "breezy.hr", "jobs.breezy.hr",
    "smartrecruiters.com", "jobs.smartrecruiters.com",
    "icims.com", "careers.icims.com",
    "ultipro.com", "recruiting.ultipro.com",
    "taleo.net", "tbe.taleo.net",
    "bamboohr.com", "jobs.bamboohr.com",
    "fountain.com", "hire.fountain.com",
    "wd1.myworkdaysite.com", "wd5.myworkdaysite.com",
}

NOTIFY_WINDOW_DAYS = 14


def within_notify_window(
    job: JobRecord,
    *,
    days: int | None = None,
    now: datetime | None = None,
) -> bool:
    """Return True if job.first_seen_at is within the notify window.

    Older jobs are still stored; they just skip alerts. Missing/unparseable
    timestamps are treated as fresh (notify) so we never drop a new listing.
    """
    window = days if days is not None else int(
        (os.environ.get("JOBRADAR_NOTIFY_WINDOW_DAYS") or str(NOTIFY_WINDOW_DAYS)).strip()
        or NOTIFY_WINDOW_DAYS
    )
    if window < 0:
        return True
    raw = (job.first_seen_at or "").strip()
    if not raw:
        return True
    try:
        fs = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    if fs.tzinfo is None:
        fs = fs.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - fs) <= timedelta(days=window)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _company_slug(company: str) -> str:
    """Convert company name to expected domain slug (e.g., 'Jane Street' -> 'janestreet')."""
    slug = (company or "").lower()
    # Remove common suffixes
    for suffix in (" inc", " inc.", " llc", " corp", " corporation", " ltd", " limited", " company", " co"):
        if slug.endswith(suffix):
            slug = slug[:len(slug) - len(suffix)]
    # Remove non-alphanumeric
    slug = re.sub(r'[^a-z0-9]+', '', slug)
    return slug


def domain_matches_company(company: str, url: str) -> bool:
    """
    Check if URL domain matches company name.
    Returns True if:
    - Domain contains company slug (e.g., 'stripe.com' matches 'Stripe')
    - URL is on recruiting platform AND path contains company slug
    - Company is too short/generic to validate
    """
    if not company or not url:
        return True  # Can't validate, allow
    
    domain = _extract_domain(url)
    if not domain:
        return True
    
    company_slug = _company_slug(company)
    if len(company_slug) < 3:
        return True  # Too short to validate reliably
    
    # Check if domain contains company slug
    if company_slug in domain:
        return True
    
    # Check if it's a recruiting platform
    for recruiting_host in RECRUITING_HOSTS:
        if recruiting_host in domain:
            # For recruiting platforms, company slug MUST be in the URL path
            if company_slug in url.lower():
                return True
            # Mismatch: recruiting platform but company not in path
            return False
    
    # Domain doesn't match company
    return False


def sanitize_job_url(url: str) -> str:
    """Strip trailing junk from URLs (quotes, angle brackets, etc)."""
    url = (url or "").strip()
    # Remove trailing quotes, parentheses, brackets, and other artifacts
    while url and url[-1] in ('"', "'", ">", ")", "`", "\\", ",", ";", "]"):
        url = url[:-1]
    return url.strip()


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return _HTML_TAG.sub("", text or "").strip()


def link_probe_enabled() -> bool:
    """Check if live link probing is enabled (default: yes, unless JOBRADAR_LINK_PROBE=0)."""
    return os.environ.get("JOBRADAR_LINK_PROBE", "1").strip() != "0"


def probe_url(url: str, *, timeout: float = 3.0) -> bool:
    """
    HTTP HEAD/GET probe. Returns True if 2xx, False otherwise.
    Requires 2xx; skip 404; 403 only if job-shaped URL (has /job or /career or /position).
    """
    if not link_probe_enabled():
        return True  # Bypass probe in tests
    
    url = sanitize_job_url(url)
    if not url or not url.startswith("http"):
        return False
    
    try:
        # Try HEAD first (faster)
        resp = httpx.head(url, timeout=timeout, follow_redirects=True)
        if 200 <= resp.status_code < 300:
            return True
        if resp.status_code == 403:
            # Accept 403 if URL looks job-related
            url_lower = url.lower()
            if any(word in url_lower for word in ("job", "career", "position", "apply", "intern")):
                return True
        if resp.status_code == 404:
            return False
        
        # Some servers don't support HEAD, try GET
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        if 200 <= resp.status_code < 300:
            return True
        if resp.status_code == 403:
            url_lower = url.lower()
            if any(word in url_lower for word in ("job", "career", "position", "apply", "intern")):
                return True
        
        return False
    except Exception as exc:
        log.debug("probe_url failed for %s: %s", url, exc)
        return False


def job_notify_block_reason(job: JobRecord) -> str | None:
    """
    Check if job should be blocked from notification. Returns block reason or None if OK.
    This is the quality gate BEFORE Discord/ntfy/Telegram.
    """
    # Check for HTML tags in company/title
    if _HTML_TAG.search(job.company or ""):
        return f"HTML in company: {job.company[:100]}"
    if _HTML_TAG.search(job.title or ""):
        return f"HTML in title: {job.title[:100]}"
    
    # Check URL
    url = sanitize_job_url(job.url)
    if not url:
        return "empty URL"
    
    url_lower = url.lower()
    if "example.com" in url_lower or "example.org" in url_lower:
        return "test fixture URL (example.com/org)"
    
    # Check domain/company mismatch
    if not domain_matches_company(job.company, url):
        domain = _extract_domain(url)
        return f"domain mismatch: company '{job.company}' vs URL domain '{domain}'"
    
    # HTTP probe
    if not probe_url(url):
        return f"URL probe failed: {url}"
    
    return None


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
        
        # Quality gate: check if job should be blocked
        block_reason = job_notify_block_reason(job)
        if block_reason:
            log.info("skipping notify for %s: %s", job.canonical_key, block_reason)
            return False
        
        # Sanitize URL before notifying
        job.url = sanitize_job_url(job.url)
        
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
