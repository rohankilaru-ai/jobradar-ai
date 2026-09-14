"""Parsers for GitHub internship listing sources."""

from __future__ import annotations

import json
from datetime import datetime
import re
from html.parser import HTMLParser
from typing import Any, Iterable

from jobradar.models import JobRecord

_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = _TAG.sub(" ", text or "")
    text = text.replace("&amp;", "&").replace("&nbsp;", " ").replace("<br>", ", ").replace("<br/>", ", ")
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
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("aprameyak listings.json must be a list")
    out: list[JobRecord] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or "").strip()
        title = str(item.get("role") or item.get("title") or "").strip()
        if not company or not title:
            continue
        posted = str(item.get("date_added") or item.get("posted_at") or item.get("date") or "").strip()
        out.append(
            JobRecord(
                company=company,
                title=title,
                location=str(item.get("location") or "").strip(),
                url=str(item.get("url") or "").strip(),
                sources=[source],
                snippet=f"{title} @ {company}",
                season=str(item.get("season") or item.get("type") or "").strip(),
                posted_at=posted,
            )
        )
    return out


def parse_dreamwork_json(raw: str | bytes, source: str = "dreamwork-2027") -> list[JobRecord]:
    data = json.loads(raw)
    listings = data.get("listings") if isinstance(data, dict) else data
    if not isinstance(listings, list):
        raise ValueError("dreamwork payload missing listings list")
    out: list[JobRecord] = []
    for item in listings:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or "").strip()
        title = str(item.get("title") or "").strip()
        if not company or not title:
            continue
        posted = str(item.get("date_added") or item.get("posted_at") or item.get("date") or item.get("created_at") or "").strip()
        out.append(
            JobRecord(
                company=company,
                title=title,
                location=str(item.get("location") or "").strip(),
                url=str(item.get("url") or "").strip(),
                sources=[source],
                snippet=f"{title} @ {company}",
                posted_at=posted,
            )
        )
    return out


def parse_applyguy_json(raw: str | bytes, source: str = "applyguy-2027") -> list[JobRecord]:
    data = json.loads(raw)
    jobs = data.get("jobs") if isinstance(data, dict) else data
    if not isinstance(jobs, list):
        raise ValueError("applyguy payload missing jobs list")
    out: list[JobRecord] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or "").strip()
        title = str(item.get("title") or "").strip()
        if not company or not title:
            continue
        url = str(item.get("listingUrl") or item.get("url") or "").strip()
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
    """Clean URL: strip trailing quotes and junk."""
    url = (url or "").strip()
    while url and url[-1] in ('"', "'", ">", ")", "`", "\\", ",", ";", "]"):
        url = url[:-1]
    return url.strip()


def parse_simplify_html(raw: str, source: str = "simplify-summer-2027") -> list[JobRecord]:
    """Parse Simplify/PittCSC HTML tables. Skip Inactive. Inherit company on ↳ rows. Prevent column mis-alignment."""
    parser = _SimplifyTableParser()
    parser.feed(raw)
    out: list[JobRecord] = []
    last_company = ""
    last_url = ""  # Track last URL for inherit rows
    
    for cells in parser.rows:
        if len(cells) < 3:
            continue
        
        # Extract and clean company (cell 0) - strip all HTML including links
        company_raw = _clean(cells[0])
        title = _clean(cells[1])
        location = _clean(cells[2].replace("<br>", ", ").replace("<br/>", ", ").replace("<br />", ", "))
        
        # Extract URL ONLY from application cell (cell 3), not from company cell
        # This prevents company <a href> from leaking into URL field
        app_html = cells[3] if len(cells) > 3 else ""
        url = _first_apply_url(app_html)
        url = _clean_url(url)  # Clean trailing quotes
        
        if not title:
            continue
        
        # Skip header rows
        if company_raw.lower() == "company" and title.lower() == "role":
            continue
        
        # Skip inactive postings
        if "inactive" in location.lower() or "inactive" in title.lower():
            continue
        
        # Handle ↳ inherit rows: inherit both company AND url from previous row
        if company_raw.startswith("↳") or company_raw == "↳":
            company = last_company
            # If inherit row has no URL in its app cell, use last URL
            if not url and last_url:
                url = last_url
        else:
            company = company_raw
            last_company = company
            # Update last_url only for non-inherit rows
            if url:
                last_url = url
        
        if not company:
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
    text = _MD_LINK.sub(r"\1", text or "")
    text = text.replace("**", "").replace("*", "")
    return _WS.sub(" ", text).strip()


def parse_markdown_table(raw: str, source: str = "markdown") -> list[JobRecord]:
    """Parse Vansh / SpeedyApply pipe tables. Inherit company on ↳ rows."""
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
    out: list[JobRecord] = []
    last_company = ""
    header_idx: dict[str, int] | None = None
    for line in text.splitlines():
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
            continue
        ci = header_idx.get("company", 0)
        ti = header_idx.get("title", 1)
        li = header_idx.get("location", 2)
        ui = header_idx.get("url")
        company_raw = _strip_md(cells[ci] if ci < len(cells) else "")
        title = _strip_md(cells[ti] if ti < len(cells) else "")
        location = _strip_md(cells[li] if li < len(cells) else "")
        url_cell = cells[ui] if ui is not None and ui < len(cells) else ""
        if not title:
            continue
        if company_raw.startswith("↳") or company_raw == "↳":
            company = last_company
        else:
            company = company_raw
            last_company = company
        if not company:
            continue
        url = ""
        found = _MD_URL.search(url_cell)
        if found:
            url = found.group(0).rstrip(").,")
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
