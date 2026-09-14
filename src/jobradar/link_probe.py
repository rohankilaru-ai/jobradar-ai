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
    """
    url_clean = (url or "").strip()
    if not url_clean:
        return "bad"
    if url_clean in ("TBD", "N/A", "None", "null", "undefined", ""):
        return "bad"
    if not url_clean.startswith(("http://", "https://")):
        return "bad"
    
    try:
        resp = httpx.head(url_clean, timeout=timeout, follow_redirects=True)
        if 200 <= resp.status_code < 400:
            return "good"
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
