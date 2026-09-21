"""URL health probe helpers for JobRadar.

Provides link verification to prevent alerts for dead/empty/bad URLs.
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx

log = logging.getLogger("jobradar.link_probe")

ProbeResult = Literal["good", "bad", "error"]


def probe_url(url: str, timeout: float = 8.0) -> ProbeResult:
    """Probe a URL via HEAD or GET. Returns 'good', 'bad', or 'error'.
    
    - 'good': 2xx/3xx response
    - 'bad': 4xx/5xx response
    - 'error': network/timeout failure
    
    Tries HEAD first (faster), falls back to GET if HEAD fails (some servers don't support HEAD).
    """
    url_clean = (url or "").strip()
    if not url_clean:
        return "bad"
    if url_clean in ("TBD", "N/A", "None", "null", "undefined", ""):
        return "bad"
    if not url_clean.startswith(("http://", "https://")):
        return "bad"
    
    try:
        # Try HEAD first (faster)
        resp = httpx.head(url_clean, timeout=timeout, follow_redirects=True)
        if 200 <= resp.status_code < 400:
            return "good"
        
        # Some servers don't support HEAD (405, 501) - try GET
        if resp.status_code in (405, 501):
            log.debug("HEAD not supported for %s, trying GET", url_clean)
            try:
                resp = httpx.get(url_clean, timeout=timeout, follow_redirects=True)
                if 200 <= resp.status_code < 400:
                    return "good"
            except Exception as exc:
                log.debug("GET fallback failed for %s: %s", url_clean, exc)
                return "error"
        
        return "bad"
    except httpx.TimeoutException:
        log.debug("probe timeout: %s", url_clean)
        return "error"
    except httpx.HTTPError as exc:
        log.debug("probe http error: %s %s", url_clean, exc)
        return "error"
    except Exception as exc:
        log.warning("probe unexpected error: %s %s", url_clean, exc)
        return "error"


def probe_url_for_notify(url: str, *, timeout: float = 3.0) -> bool:
    """
    Probe URL for notify gates. Returns True if acceptable, False otherwise.
    
    Uses probe_url for core checking, then adds notify-specific logic:
    - Accept 403 for job-shaped URLs (common ATS behavior)
    - Map: good → True, bad/error → False (with 403 exception)
    
    This helper unifies verify-links and notify probe logic.
    """
    result = probe_url(url, timeout=timeout)
    
    if result == "good":
        return True
    elif result == "error":
        return False
    else:  # result == "bad"
        # Notify-specific: accept 403 for job-shaped URLs
        try:
            resp = httpx.head(url, timeout=timeout, follow_redirects=True)
            if resp.status_code == 403:
                url_lower = url.lower()
                if any(word in url_lower for word in ("job", "career", "position", "apply", "intern")):
                    return True
        except Exception:
            pass
        return False


def is_placeholder_url(url: str) -> bool:
    """Check if URL is empty or a known placeholder."""
    url_clean = (url or "").strip().lower()
    if not url_clean:
        return True
    if url_clean in ("tbd", "n/a", "none", "null", "undefined", ""):
        return True
    if not url_clean.startswith(("http://", "https://")):
        return True
    return False
