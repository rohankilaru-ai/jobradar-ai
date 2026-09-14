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
from email.header import Header
from urllib.parse import quote, urlparse

import httpx

from jobradar.db import Database
from jobradar.link_probe import is_placeholder_url
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

BAD_URL_PATTERNS = [
    r"example\.com",
    r"example\.org",
    r"localhost",
    r"127\.0\.0\.1",
    r"test\.com",
    r"placeholder",
]


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


def is_specific_job_url(url: str | None) -> bool:
    """
    Check if URL points to a specific job posting (not a generic career search/listing page).
    
    Returns False (block) for:
    - dreamworkhq.com (aggregator, not employer ATS)
    - Generic career homepages: /careers, /jobs (without job identifier)
    - Search/listing pages: /careers/search, /jobs/results, /careers?query=, etc.
    
    Returns True (allow) for:
    - Known ATS platforms with job identifiers (Greenhouse, Lever, Ashby, Workday, iCIMS, etc.)
    - Company pages with job identifiers: gh_jid=, job_id=, /position/, /job/ID
    """
    if not url:
        return False
    
    url = sanitize_job_url(url)
    if not url or not url.startswith("http"):
        return False
    
    url_lower = url.lower()
    parsed = urlparse(url_lower)
    domain = parsed.netloc.lstrip("www.")
    path = parsed.path.rstrip("/")
    query = parsed.query
    
    # Block: dreamworkhq.com is an aggregator, not an employer ATS
    if "dreamworkhq.com" in domain:
        return False
    
    # Allow: Known ATS platforms with job-specific paths
    # Greenhouse: /jobs/ID or gh_jid parameter
    if "greenhouse.io" in domain or "gh_jid=" in query:
        if "/jobs/" in path or "gh_jid=" in query:
            return True
    
    # Lever: /company/slug
    if "lever.co" in domain and path.count("/") >= 2:
        return True
    
    # Ashby: /company/uuid
    if "ashbyhq.com" in domain and path.count("/") >= 2:
        return True
    
    # Workday: /job/ in path
    if "workday" in domain and "/job" in path:
        return True
    
    # iCIMS: /job in path or job= in query
    if "icims.com" in domain:
        if "/job" in path or "job=" in query:
            return True
    
    # Amazon Jobs: /jobs/ with identifier
    if "amazon.jobs" in domain and "/jobs/" in path:
        return True
    
    # Taleo: job= or job ID parameter
    if "taleo.net" in domain and ("job=" in query or "/jobdetail" in path):
        return True
    
    # SmartRecruiters: /jobs/ or job ID in path
    if "smartrecruiters.com" in domain and path.count("/") >= 2:
        return True
    
    # JobVite, BambooHR, Breezy, Fountain: job identifier in path
    if any(ats in domain for ats in ("jobvite.com", "bamboohr.com", "breezy.hr", "fountain.com")):
        if path.count("/") >= 2:
            return True
    
    # Generic job identifiers in query parameters
    job_params = ("gh_jid=", "job_id=", "jobid=", "id=", "job=", "position=", "requisition")
    if any(param in query for param in job_params):
        # Make sure it's not just a search query
        if "query=" not in query and "search=" not in query and "q=" not in query:
            return True
    
    # /position/ path (e.g., Jane Street)
    if "/position/" in path:
        return True
    
    # Block: Generic career search/listing keywords in path
    blocking_keywords = [
        "search", "results", "openings", "listings", "opportunities",
        "search-results", "job-search", "career-search"
    ]
    path_segments = [seg for seg in path.split("/") if seg]
    
    # Check if blocking keywords appear in path
    for i, segment in enumerate(path_segments):
        if segment in blocking_keywords:
            # Check if there's an ID-like segment after this keyword
            # e.g., /jobs/results/123456 should be allowed
            if i + 1 < len(path_segments):
                next_segment = path_segments[i + 1]
                # If next segment looks like an ID (all digits or long alphanumeric), allow it
                if next_segment.isdigit() or (len(next_segment) > 6 and any(c.isdigit() for c in next_segment)):
                    # Has ID after blocking keyword - likely specific job
                    continue
            # No ID after blocking keyword - generic page
            return False
    
    # /job/ or /jobs/ followed by identifier (not just listing pages)
    if "/job/" in path or "/jobs/" in path:
        # Check for blocking patterns like /jobs/results, /jobs/search
        # But allow them if followed by an ID (e.g., /jobs/results/123456)
        blocking_patterns = [
            "/jobs/results", "/jobs/search", "/jobs/openings", "/jobs/listings",
            "/job/results", "/job/search",
            "/careers/search", "/careers/results", "/careers/openings",
        ]
        
        has_blocking_pattern = False
        for pattern in blocking_patterns:
            if pattern in path:
                has_blocking_pattern = True
                # Check if there's an ID-like segment after this pattern
                after = path.split(pattern, 1)[1].lstrip("/")
                if after:
                    first_segment_after = after.split("/")[0]
                    # If it's a numeric ID or long alphanumeric, it's likely a specific job
                    if first_segment_after.isdigit() or (len(first_segment_after) > 6 and any(c.isdigit() for c in first_segment_after)):
                        has_blocking_pattern = False  # Don't block this one
                        break
                # If we get here, pattern is in path but no ID after - will block below
                break
        
        if has_blocking_pattern:
            return False
        
        # If /job/ or /jobs/ has more path segments (likely specific posting)
        # e.g., /jobs/123456 or /job/software-engineer
        parts = [p for p in path.split("/") if p]
        if "/job" in path:
            job_index = next((i for i, p in enumerate(parts) if "job" in p), -1)
            if job_index >= 0 and job_index + 1 < len(parts):
                # Has something after /job or /jobs
                next_segment = parts[job_index + 1]
                # Not a generic listing page
                if next_segment not in ("results", "search", "openings", "listings"):
                    return True
    
    # Block: Generic career homepages
    blocking_paths = [
        "/careers", "/careers/", 
        "/jobs", "/jobs/",
        "/career", "/career/",
        "/work-with-us", "/join-us",
        "/careers/search", "/jobs/search",
        "/careers/openings", "/jobs/openings",
        "/careers/job-search", "/job-search",
        "/job-listings", "/job-opportunities",
    ]
    
    # Exact path match for blocking
    if path in blocking_paths:
        return False
    
    # Block if query contains search-related parameters without job identifiers
    if query:
        search_params = ("query=", "search=", "q=", "keyword=")
        if any(param in query for param in search_params):
            # It's a search page
            return False
    
    # Default: allow (better to have false positives than miss real jobs)
    return True


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
    if is_placeholder_url(url):
        return f"placeholder URL: {url[:80]}"
    
    url_lower = url.lower()
    if "example.com" in url_lower or "example.org" in url_lower:
        return "test fixture URL (example.com/org)"
    
    # Check if URL is a specific job posting (not generic career page)
    if not is_specific_job_url(url):
        return f"generic career page, not a specific job posting: {url[:80]}"
    
    # Check domain/company mismatch
    if not domain_matches_company(job.company, url):
        domain = _extract_domain(url)
        return f"domain mismatch: company '{job.company}' vs URL domain '{domain}'"
    
    # HTTP probe
    if not probe_url(url):
        return f"URL probe failed: {url}"
    
    return None


def is_link_probe_enabled() -> bool:
    """Alias for link_probe_enabled (PR #7 / backlog tests)."""
    return link_probe_enabled()

def is_url_quality_good(url: str) -> bool:
    """Lightweight URL quality check (empty / example / invalid scheme)."""
    url = (url or "").strip()
    if not url:
        return False
    url_lower = url.lower()
    for pattern in BAD_URL_PATTERNS:
        if re.search(pattern, url_lower):
            return False
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
    except Exception:
        return False
    return True

def should_send_alerts(job: JobRecord) -> bool:
    """Discord/ntfy/Telegram only when inside notify window AND main quality gates pass."""
    if not within_notify_window(job):
        log.debug("Job outside notify window: %s", job.canonical_key)
        return False
    block = job_notify_block_reason(job)
    if block:
        log.debug("Job blocked from alerts (%s): %s", block, job.canonical_key)
        return False
    return True


def is_within_notify_window(job: JobRecord) -> bool:
    """Alias used by backlog notify tests."""
    return within_notify_window(job)


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
    # Safety: Never send to live Discord during pytest (even if DISCORD_WEBHOOK_URL is set)
    if os.environ.get("PYTEST_CURRENT_TEST"):
        log.debug("send_discord: blocked (PYTEST_CURRENT_TEST is set)")
        return "skipped"
    url = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    if not url:
        return "skipped"
    resp = httpx.post(url, json={"content": text[:1900]}, timeout=8.0)
    if resp.status_code >= 400:
        raise RuntimeError(f"discord HTTP {resp.status_code}")
    return "ok"


def _ntfy_header_value(value: str, max_len: int = 200) -> str:
    """Encode ntfy header values as ASCII (RFC 2047) so em-dashes etc. do not break."""
    value = (value or "")[:max_len]
    try:
        value.encode("ascii")
        return value
    except UnicodeEncodeError:
        return Header(value, "utf-8").encode()


def send_ntfy(text: str, *, priority: bool = False, title: str = "JobRadar") -> str:
    """Free phone push via ntfy.sh (or self-hosted NTFY_SERVER)."""
    # Safety: Never send to live ntfy during pytest (even if NTFY_TOPIC is set)
    if os.environ.get("PYTEST_CURRENT_TEST"):
        log.debug("send_ntfy: blocked (PYTEST_CURRENT_TEST is set)")
        return "skipped"
    topic = (os.environ.get("NTFY_TOPIC") or "").strip()
    if not topic:
        return "skipped"
    server = (os.environ.get("NTFY_SERVER") or "https://ntfy.sh").strip().rstrip("/")
    url = f"{server}/{quote(topic, safe='')}"
    headers = {
        "Title": _ntfy_header_value(title, 200),
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
    # Safety: Never send to live Telegram during pytest (even if TELEGRAM_BOT_TOKEN is set)
    if os.environ.get("PYTEST_CURRENT_TEST"):
        log.debug("send_telegram: blocked (PYTEST_CURRENT_TEST is set)")
        return "skipped"
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

    def notify(self, job: JobRecord, *, silent: bool = False) -> bool:
        """Notify about a job. If silent=True, only write JSONL (no Discord/ntfy/Telegram)."""
        if self.db and self.db.was_notified(job.canonical_key):
            return False

        if not silent:
            # Quality gate: check if job should be blocked (main/#3 gates)
            block_reason = job_notify_block_reason(job)
            if block_reason:
                log.info("skipping notify for %s: %s", job.canonical_key, block_reason)
                return False
            job.url = sanitize_job_url(job.url)

        payload = format_alert(job)
        record = {
            "ts": _now(),
            "channel": "jsonl",
            "canonical_key": job.canonical_key,
            "priority": job.priority,
            "text": payload,
            "job": job.webhook_payload()["job"],
            "silent": silent,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if self.db:
            self.db.record_notification(job.canonical_key, "jsonl", payload, record["ts"])

        if silent:
            log.debug("Silent notification (JSONL only): %s", job.canonical_key)
            return True

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
