"""Parsers for GitHub internship listing sources."""

from __future__ import annotations

import json
from datetime import datetime
import re
from html.parser import HTMLParser
from html import unescape as html_unescape
from typing import Any, Iterable
import logging

from jobradar.models import JobRecord, is_bad_url

log = logging.getLogger("jobradar.parsers")

_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
# Match HTML tags: <tagname ...> or </tagname>
# This avoids matching bare angle brackets like "<Best>" which might be text content
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    """Clean HTML text: strip tags, decode entities, normalize whitespace."""
    text = text or ""
    # Strip script and style tags along with their content
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.DOTALL)
    # Strip all remaining HTML tags
    text = _TAG.sub(" ", text)
    # Decode HTML entities (handles &amp;, &lt;, &gt;, &quot;, &apos;, &#39;, &#NNN;, etc.)
    text = html_unescape(text)
    # Replace common breaks with commas
    text = text.replace("<br>", ", ").replace("<br/>", ", ")
    # Normalize whitespace
    return _WS.sub(" ", text).strip()



_AGE_TOKEN = re.compile(
    r"^(\d+)\s*(mo|mos|months?|hours?|hrs?|days?|weeks?|wks?|[hdwm])$",
    re.I,
)


def age_token_to_posted_at(token: str, *, now: datetime | None = None) -> str:
    """Convert Simplify-style age tokens (12d, 3h, 1mo) to an ISO date string; empty if unknown."""
    from datetime import datetime, timezone, timedelta
    raw = (token or "").strip()
    if not raw:
        return ""
    # already a date
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    m = _AGE_TOKEN.match(raw)
    if not m:
        return ""
    n = int(m.group(1))
    unit = m.group(2).lower()
    now = now or datetime.now(timezone.utc)
    if unit in {"h", "hr", "hrs", "hour", "hours"}:
        dt = now - timedelta(hours=n)
    elif unit in {"d", "day", "days"}:
        dt = now - timedelta(days=n)
    elif unit in {"w", "wk", "wks", "week", "weeks"}:
        dt = now - timedelta(weeks=n)
    elif unit in {"m", "mo", "mos", "month", "months"}:
        dt = now - timedelta(days=30 * n)
    else:
        return ""
    return dt.date().isoformat()

def parse_aprameyak_json(raw: str | bytes, source: str = "aprameyak-2027") -> list[JobRecord]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        preview = (raw[:100] if isinstance(raw, str) else raw[:100].decode("utf-8", errors="ignore")) if raw else ""
        log.error(
            "JSON decode error in %s at line %d col %d: %s. Preview: %r",
            source, e.lineno, e.colno, e.msg, preview
        )
        return []
    except (UnicodeDecodeError, ValueError) as e:
        preview = (raw[:100] if isinstance(raw, str) else raw[:100].decode("utf-8", errors="ignore")) if raw else ""
        log.error(
            "Parse error in %s: %s. Preview: %r",
            source, str(e), preview
        )
        return []
    if not isinstance(data, list):
        log.warning("%s: expected list, got %s. Skipping.", source, type(data).__name__)
        return []
    out: list[JobRecord] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or "").strip()
        title = str(item.get("role") or item.get("title") or "").strip()
        if not company or not title:
            continue
        url = str(item.get("url") or "").strip()
        url = _clean_url(url)  # Clean and validate
        posted = str(item.get("date_added") or item.get("posted_at") or item.get("date") or "").strip()
        out.append(
            JobRecord(
                company=company,
                title=title,
                location=str(item.get("location") or "").strip(),
                url=url,
                sources=[source],
                snippet=f"{title} @ {company}",
                season=str(item.get("season") or item.get("type") or "").strip(),
                posted_at=posted,
            )
        )
    return out


def parse_dreamwork_json(raw: str | bytes, source: str = "dreamwork-2027") -> list[JobRecord]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        preview = (raw[:100] if isinstance(raw, str) else raw[:100].decode("utf-8", errors="ignore")) if raw else ""
        log.error(
            "JSON decode error in %s at line %d col %d: %s. Preview: %r",
            source, e.lineno, e.colno, e.msg, preview
        )
        return []
    except (UnicodeDecodeError, ValueError) as e:
        preview = (raw[:100] if isinstance(raw, str) else raw[:100].decode("utf-8", errors="ignore")) if raw else ""
        log.error(
            "Parse error in %s: %s. Preview: %r",
            source, str(e), preview
        )
        return []
    listings = data.get("listings") if isinstance(data, dict) else data
    if not isinstance(listings, list):
        log.warning("%s: expected listings list, got %s. Skipping.", source, type(listings).__name__)
        return []
    out: list[JobRecord] = []
    for item in listings:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or "").strip()
        title = str(item.get("title") or "").strip()
        if not company or not title:
            continue
        url = str(item.get("url") or "").strip()
        url = _clean_url(url)  # Clean and validate
        posted = str(item.get("date_added") or item.get("posted_at") or item.get("date") or item.get("created_at") or "").strip()
        out.append(
            JobRecord(
                company=company,
                title=title,
                location=str(item.get("location") or "").strip(),
                url=url,
                sources=[source],
                snippet=f"{title} @ {company}",
                posted_at=posted,
            )
        )
    return out


def parse_applyguy_json(raw: str | bytes, source: str = "applyguy-2027") -> list[JobRecord]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        preview = (raw[:100] if isinstance(raw, str) else raw[:100].decode("utf-8", errors="ignore")) if raw else ""
        log.error(
            "JSON decode error in %s at line %d col %d: %s. Preview: %r",
            source, e.lineno, e.colno, e.msg, preview
        )
        return []
    except (UnicodeDecodeError, ValueError) as e:
        preview = (raw[:100] if isinstance(raw, str) else raw[:100].decode("utf-8", errors="ignore")) if raw else ""
        log.error(
            "Parse error in %s: %s. Preview: %r",
            source, str(e), preview
        )
        return []
    jobs = data.get("jobs") if isinstance(data, dict) else data
    if not isinstance(jobs, list):
        log.warning("%s: expected jobs list, got %s. Skipping.", source, type(jobs).__name__)
        return []
    out: list[JobRecord] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or "").strip()
        title = str(item.get("title") or "").strip()
        if not company or not title:
            continue
        url = str(item.get("listingUrl") or item.get("url") or "").strip()
        url = _clean_url(url)  # Clean and validate
        posted = str(item.get("date_added") or item.get("posted_at") or item.get("date") or item.get("createdAt") or "").strip()
        out.append(
            JobRecord(
                company=company,
                title=title,
                location=str(item.get("location") or "").strip(),
                url=url,
                sources=[source],
                snippet=f"{title} @ {company}",
                season=str(item.get("season") or "").strip(),
                posted_at=posted,
            )
        )
    return out


class _SimplifyTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_td = False
        self.in_tr = False
        self.cell_html: list[str] = []
        self.row_cells: list[str] = []
        self.rows: list[list[str]] = []
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.in_tr = True
            self.row_cells = []
        elif tag == "td" and self.in_tr:
            self.in_td = True
            self._buf = []
            # keep attrs for href extraction via raw reconstruction
            attr_s = "".join(f' {k}="{v}"' for k, v in attrs if v is not None)
            self._buf.append(f"<{tag}{attr_s}>")
        elif self.in_td:
            attr_s = "".join(f' {k}="{v}"' for k, v in attrs if v is not None)
            self._buf.append(f"<{tag}{attr_s}>")

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_td:
            self._buf.append(f"</{tag}>")
            self.row_cells.append("".join(self._buf))
            self.in_td = False
            self._buf = []
        elif self.in_td:
            self._buf.append(f"</{tag}>")
        elif tag == "tr" and self.in_tr:
            if self.row_cells:
                self.rows.append(self.row_cells)
            self.in_tr = False
            self.row_cells = []

    def handle_data(self, data: str) -> None:
        if self.in_td:
            self._buf.append(data)


def _first_apply_url(cell_html: str) -> str:
    """Extract first real job posting URL from application cell, skip Simplify redirects."""
    for m in _HREF.finditer(cell_html or ""):
        href = m.group(1)
        # Skip Simplify's tracking redirects
        if "simplify.jobs/c/" in href or "simplify.jobs/p/" in href:
            continue
        if href.startswith("http"):
            return href
    return ""


def _clean_url(url: str) -> str:
    """Clean URL: strip trailing/leading quotes and junk, validate against bad URLs."""
    url = (url or "").strip()
    # Strip trailing junk
    while url and url[-1] in ('"', "'", ">", ")", "`", "\\", ",", ";", "]"):
        url = url[:-1]
    # Strip leading junk too
    while url and url[0] in ('"', "'", "<", "{", "["):
        url = url[1:]
    url = url.strip()
    
    # Reject URLs with embedded whitespace or newlines (but allow %20 encoding)
    if url and any(c in url for c in (" ", "\t", "\n", "\r")):
        log.debug("Rejected URL with embedded whitespace: %s", url[:100])
        return ""
    
    # Early validation: return empty string if bad URL
    if url and is_bad_url(url):
        log.debug("Rejected bad URL at parse time: %s", url[:100])
        return ""
    return url


def parse_simplify_html(raw: str, source: str = "simplify-summer-2027") -> list[JobRecord]:
    """Parse Simplify/PittCSC HTML tables. Skip Inactive. Inherit company on ↳ rows. Prevent column mis-alignment."""
    parser = _SimplifyTableParser()
    try:
        parser.feed(raw)
    except Exception as e:
        log.warning("HTML parser error, attempting to continue: %s", e)
    
    out: list[JobRecord] = []
    last_company = ""
    last_url = ""  # Track last URL for inherit rows
    
    for row_idx, cells in enumerate(parser.rows):
        # Guard: Need at least company, title, location columns (cell 0, 1, 2)
        if len(cells) < 3:
            log.debug("Skipping row %d: insufficient columns (%d)", row_idx, len(cells))
            continue
        
        # Extract and clean company (cell 0) - strip all HTML including links
        company_raw = _clean(cells[0])
        title = _clean(cells[1])
        location = _clean(cells[2].replace("<br>", ", ").replace("<br/>", ", ").replace("<br />", ", "))
        
        # Extract URL ONLY from application cell (cell 3), not from company cell
        # This prevents company <a href> from leaking into URL field
        app_html = cells[3] if len(cells) > 3 else ""
        url = _first_apply_url(app_html)
        url = _clean_url(url)  # Clean and validate
        
        if not title:
            log.debug("Skipping row %d: empty title", row_idx)
            continue
        
        # Skip header rows
        if company_raw.lower() == "company" and title.lower() == "role":
            continue
        
        # Skip inactive postings (check both location and title)
        if "inactive" in location.lower() or "inactive" in title.lower() or "inactive" in company_raw.lower():
            log.debug("Skipping inactive row: %s | %s", company_raw, title)
            continue
        
        # Handle ↳ inherit rows: inherit both company AND url from previous row
        # Guard: if we have no last_company, skip the inherit row
        # Only treat explicit ↳ as inherit marker, not empty cells
        is_inherit = company_raw.startswith("↳") or company_raw == "↳"
        if is_inherit:
            if not last_company:
                log.debug("Skipping row %d: inherit marker but no previous company", row_idx)
                continue
            company = last_company
            # If inherit row has no URL in its app cell, use last URL
            if not url and last_url:
                url = last_url
        else:
            company = company_raw
            if company:
                last_company = company
            # Update last_url only for non-inherit rows
            if url:
                last_url = url
        
        if not company:
            log.debug("Skipping row %d: empty company after inheritance", row_idx)
            continue
        
        is_closed = "🔒" in title or "closed" in title.lower()
        # Age often lives in the last cell(s) after Application (e.g. 12d)
        age_raw = ""
        for cell in cells[4:]:
            tok = _clean(cell)
            if age_token_to_posted_at(tok):
                age_raw = tok
                break
            if _AGE_TOKEN.match(tok.strip()):
                age_raw = tok.strip()
                break
        posted = age_token_to_posted_at(age_raw)
        out.append(
            JobRecord(
                company=company,
                title=title.replace("🔒", "").strip(),
                location=location,
                url=url,
                sources=[source],
                snippet=f"{title} @ {company}",
                is_closed=is_closed,
                posted_at=posted,
            )
        )
    return out


_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_URL = re.compile(r"https?://[^\s)<>]+")
_PIPE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")


def _strip_md(text: str) -> str:
    """Strip markdown formatting and decode HTML entities."""
    text = _MD_LINK.sub(r"\1", text or "")
    text = text.replace("**", "").replace("*", "")
    # Decode HTML entities (markdown can contain &amp;, &lt;, etc.)
    text = html_unescape(text)
    return _WS.sub(" ", text).strip()


def parse_markdown_table(raw: str, source: str = "markdown") -> list[JobRecord]:
    """Parse Vansh / SpeedyApply pipe tables. Inherit company on ↳ rows."""
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
    out: list[JobRecord] = []
    last_company = ""
    last_url = ""  # Track last URL for inherit rows
    header_idx: dict[str, int] | None = None
    line_num = 0
    for line in text.splitlines():
        line_num += 1
        m = _PIPE_ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if not cells or all(set(c) <= set("-: ") for c in cells):
            continue
        lower = [c.lower() for c in cells]
        if header_idx is None and any("company" in c for c in lower):
            header_idx = {}
            for i, name in enumerate(lower):
                if "company" in name:
                    header_idx["company"] = i
                elif name in {"role", "position", "title"} or "role" in name:
                    header_idx["title"] = i
                elif "location" in name:
                    header_idx["location"] = i
                elif any(k in name for k in ("application", "link", "posting", "url")):
                    header_idx["url"] = i
                elif name.strip() in {"age", "date", "posted", "added"} or "age" == name.strip():
                    header_idx["age"] = i
            continue
        if header_idx is None:
            log.debug("Skipping line %d: no header found yet", line_num)
            continue
        
        # Extract fields with bounds checking
        ci = header_idx.get("company", 0)
        ti = header_idx.get("title", 1)
        li = header_idx.get("location", 2)
        ui = header_idx.get("url")
        
        company_raw = _strip_md(cells[ci] if ci < len(cells) else "")
        title = _strip_md(cells[ti] if ti < len(cells) else "")
        location = _strip_md(cells[li] if li < len(cells) else "")
        url_cell = cells[ui] if ui is not None and ui < len(cells) else ""
        
        if not title:
            log.debug("Skipping line %d: empty title", line_num)
            continue
        
        # Handle ↳ inherit rows: inherit both company AND url from previous row
        # Guard: if we have no last_company, skip the inherit row
        # Only treat explicit ↳ as inherit marker, not empty cells
        is_inherit = company_raw.startswith("↳") or company_raw == "↳"
        if is_inherit:
            if not last_company:
                log.debug("Skipping line %d: inherit marker but no previous company", line_num)
                continue
            company = last_company
        else:
            company = company_raw
            if company:
                last_company = company
        
        if not company:
            log.debug("Skipping line %d: empty company after inheritance", line_num)
            continue
        
        # Extract and clean URL
        url = ""
        found = _MD_URL.search(url_cell)
        if found:
            url = found.group(0).rstrip(").,")
            url = _clean_url(url)  # Clean and validate
        
        # If inherit row and no URL found, use last URL
        if not url and is_inherit and last_url:
            url = last_url
        
        # Update last_url for non-inherit rows
        if url and not is_inherit:
            last_url = url
        
        is_closed = "🔒" in title or "closed" in title.lower()
        ai = header_idx.get("age")
        age_cell = _strip_md(cells[ai]) if ai is not None and ai < len(cells) else ""
        posted = age_token_to_posted_at(age_cell)
        out.append(
            JobRecord(
                company=company,
                title=title.replace("🔒", "").strip(),
                location=location,
                url=url,
                sources=[source],
                snippet=f"{title} @ {company}",
                is_closed=is_closed,
                posted_at=posted,
            )
        )
    return out


def parse_source(kind: str, raw: str | bytes, source_name: str | None = None) -> list[JobRecord]:
    kind = kind.lower()
    if kind in {"aprameyak", "aprameyak-json"}:
        return parse_aprameyak_json(raw, source_name or "aprameyak-2027")
    if kind in {"dreamwork", "dreamwork-json"}:
        return parse_dreamwork_json(raw, source_name or "dreamwork-2027")
    if kind in {"applyguy", "applyguy-json"}:
        return parse_applyguy_json(raw, source_name or "applyguy-2027")
    if kind in {"markdown", "markdown_table", "vansh", "speedyapply"}:
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        return parse_markdown_table(text, source_name or "markdown")
    if kind in {"simplify", "simplify-html", "html"}:
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        return parse_simplify_html(text, source_name or "simplify-summer-2027")
    raise ValueError(f"unknown parser kind: {kind}")
