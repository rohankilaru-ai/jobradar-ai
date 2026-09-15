"""Gmail classify + label. Rules first. Never used as an alert channel.

Canonical labels are nested under JobRadar/:
  JobRadar/Applied, JobRadar/OA, JobRadar/Interview, JobRadar/Final Round,
  JobRadar/Offer, JobRadar/Rejected, JobRadar/Waiting, JobRadar/Recruiter,
  JobRadar/Ghosted, JobRadar/Backlog
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.tier import classify_company_tier

log = logging.getLogger("jobradar.gmail")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Nested status labels (canonical). Parent "JobRadar" is also ensured.
LABEL_PREFIX = "JobRadar"
STATUS_LABELS = (
    "Applied",
    "Interview",
    "OA",
    "Final Round",
    "Rejected",
    "Offer",
    "Recruiter",
    "Waiting",
    "Ghosted",
    "Backlog",
)

# Flat labels from older runs — migrate away; do not create.
LEGACY_FLAT_LABELS = frozenset(
    {"Applied", "Interview", "OA", "Rejected", "Offer", "Recruiter", "Waiting", "Job Oriented"}
)

STATUS_FOR = {
    "applied": "Applied",
    "interview": "Interview",
    "oa": "OA",
    "final_round": "Final Round",
    "rejected": "Rejected",
    "offer": "Offer",
    "recruiter": "Recruiter",
    "waiting": "Waiting",
    "ghosted": "Ghosted",
    "other": "Seen",
}

RULES: list[tuple[str, tuple[str, ...]]] = [
    ("rejected", ("unfortunately", "not moving forward", "other candidates", "we regret", "will not be moving", "decided not to move")),
    ("offer", ("offer letter", "pleased to offer", "congratulations on your offer")),
    ("final_round", ("final round", "final interview", "onsite interview", "superday")),
    ("oa", ("hackerrank", "codesignal", "codility", "online assessment", "oa invite", "coding assessment", "hirevue")),
    ("interview", ("interview", "phone screen", "phone-screen", "schedule a call", "virtual onsite", "next step for your")),
    ("applied", ("thanks for applying", "thank you for applying", "we received your application", "application received", "successfully submitted application", "application is being reviewed", "confirm that we've received")),
    ("recruiter", ("talent acquisition", "i'd like to connect", "reaching out about", "recruiting team", "recruiter at")),
    ("waiting", ("under review", "still reviewing", "added to our database")),
    ("ghosted", ("closing this requisition", "role has been filled", "position has been filled")),
]

ATS_HOST_FRAGMENTS = (
    "greenhouse",
    "lever.co",
    "ashbyhq",
    "myworkday",
    "workday",
    "icims",
    "smartrecruiters",
    "jobvite",
    "taleo",
    "successfactors",
    "ripplehire",
)

GENERIC_LOCAL_PARTS = frozenset(
    {
        "no-reply",
        "noreply",
        "do_not_reply",
        "donotreply",
        "mail",
        "email",
        "jobs",
        "careers",
        "recruiting",
        "notifications",
        "hello",
        "info",
        "support",
        "talent",
        "hr",
        "people",
        "workday",
        "greenhouse",
        "ashby",
    }
)

VENDOR_HOSTS = frozenset(
    {
        "greenhouse.io",
        "mail.greenhouse.io",
        "lever.co",
        "hire.lever.co",
        "ashbyhq.com",
        "myworkday.com",
        "workday.com",
        "icims.com",
        "smartrecruiters.com",
        "jobvite.com",
        "taleo.net",
        "successfactors.com",
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "yahoo.com",
        "icloud.com",
        "hotmail.com",
    }
)

ROLE_FAMILY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Quant", ("quant", "quantitative", "trading", "market maker")),
    ("ML", ("machine learning", " ml ", "ml engineer", "deep learning")),
    ("AI", ("artificial intelligence", " ai ", "ai science", "llm", "generative ai")),
    ("Research", ("research scientist", "research intern", "applied research")),
    ("DE", ("data engineer", "data engineering", "etl", "analytics engineer")),
    ("DS", ("data science", "data scientist", "data analyst", "analytics intern")),
    ("Infra", ("infrastructure", "devops", "sre", "platform engineer", "site reliability")),
    ("SWE", ("software engineer", "swe", "software engineering", "fullstack", "full stack", "backend", "frontend", "mobile software")),
]


def secrets_path() -> Path:
    return Path(os.environ.get("GMAIL_CLIENT_SECRETS", "secrets/gmail-client.json"))


def token_path() -> Path:
    return Path(os.environ.get("GMAIL_TOKEN", "secrets/gmail-token.json"))


def configured() -> bool:
    return secrets_path().is_file()


def nested_label_name(status: str) -> str:
    return f"{LABEL_PREFIX}/{status}"


def classify_email(subject: str, snippet: str = "", from_addr: str = "") -> str:
    blob = f"{subject} {snippet} {from_addr}".lower()
    for label, needles in RULES:
        if any(n in blob for n in needles):
            return label
    if any(frag in blob for frag in ATS_HOST_FRAGMENTS):
        return "applied"
    return "other"


def _clean_company(name: str) -> str:
    name = (name or "").strip(" .-_|")
    name = re.sub(r"\s+", " ", name)
    # Drop trailing boilerplate
    name = re.sub(
        r"\b(inc|llc|ltd|corp|corporation|company|co)\.?$",
        "",
        name,
        flags=re.I,
    ).strip(" .-_")
    return name[:80]


def _company_from_subject(subject: str) -> str:
    sub = re.sub(r"^(re|fw|fwd):\s*", "", (subject or "").strip(), flags=re.I)
    patterns = [
        r"(?:thank(?:s| you)? for applying(?: to)?|application received(?:!)?(?: thanks for applying to)?)\s+(.+?)(?:\s*[!|.].*)?$",
        r"(?:thanks for applying to)\s+(.+?)(?:\s*[!|.].*)?$",
        r"(?:applying to|application (?:to|for)|at)\s+([A-Z][\w .&'-]{1,60})(?:\s|$)",
        r"^(.+?)\s+[—\-–]\s+(?:internship|intern|application|thank)",
    ]
    for pat in patterns:
        m = re.search(pat, sub, flags=re.I)
        if m:
            cand = _clean_company(m.group(1))
            # Avoid grabbing role text as company
            if cand and len(cand) > 1 and not re.search(r"\bintern\b", cand, re.I):
                # Strip leading "the "
                cand = re.sub(r"^the\s+", "", cand, flags=re.I)
                # If subject was "Thanks for applying to the Summer 2027: ... Role at Intuit"
                at_m = re.search(r"\bat\s+([A-Z][\w .&'-]{1,40})$", cand, flags=re.I)
                if at_m:
                    return _clean_company(at_m.group(1))
                if "role at" in cand.lower():
                    parts = re.split(r"\brole at\s+", cand, flags=re.I)
                    if len(parts) > 1:
                        return _clean_company(parts[-1])
                return cand
    return ""


def _company_from_snippet(snippet: str) -> str:
    sn = snippet or ""
    patterns = [
        r"(?:applying to|application (?:to|for)|interest in)\s+([A-Z][\w .&'-]{1,50})",
        r"(?:position (?:of|at)|role at)\s+([A-Z][\w .&'-]{1,50})",
        r"Thank you for applying to\s+([A-Z][\w .&'-]{1,50})",
    ]
    for pat in patterns:
        m = re.search(pat, sn)
        if m:
            return _clean_company(m.group(1))
    return ""


def extract_company_guess(subject: str, from_addr: str, snippet: str = "") -> str:
    """Best-effort company name from subject/from/snippet (never ATS vendor names)."""
    # Prefer explicit subject company ("Thanks for applying to DoorDash")
    from_subject = _company_from_subject(subject)
    if from_subject:
        low = from_subject.lower()
        if low not in {"myworkday", "greenhouse", "ashbyhq", "workday", "icims"}:
            return from_subject.title() if from_subject.islower() else from_subject

    # Parse From early — Workday/ATS local parts beat role text in snippets
    addr = (from_addr or "").lower()
    m_email = re.search(r"([\w.+-]+)@([a-z0-9.-]+)", addr)
    if m_email:
        local, host = m_email.group(1), m_email.group(2)
        host = host.lstrip("www.")
        # Workday local part often encodes company: wexinc@myworkday.com
        if any(v in host for v in ("myworkday.com", "workday.com")) and local not in GENERIC_LOCAL_PARTS:
            guess = local.replace("_", " ").replace("-", " ")
            guess = re.sub(r"(inc|corp|llc)$", "", guess, flags=re.I).strip()
            if guess and guess not in GENERIC_LOCAL_PARTS:
                return _clean_company(guess).title()

        # Subdomain ATS: notifications@opportunities.keurigdrpepper.com
        parts = host.split(".")
        if len(parts) >= 3 and parts[0] in {
            "mail",
            "email",
            "jobs",
            "careers",
            "opportunities",
            "talent",
            "noreply",
            "no-reply",
        }:
            company_host = parts[1]
            if company_host not in {"gmail", "google", "outlook", "yahoo"}:
                return _clean_company(company_host.replace("-", " ")).title()

        if host not in VENDOR_HOSTS and not any(host.endswith(v) for v in VENDOR_HOSTS):
            base = parts[-2] if len(parts) >= 2 else parts[0]
            if base not in {"gmail", "googlemail", "outlook", "yahoo", "icloud", "hotmail", "com", "edu"}:
                return _clean_company(base.replace("-", " ")).title()

    from_snip = _company_from_snippet(snippet)
    if from_snip and not re.search(
        r"\b(intern|engineer|analyst|scientist|manager|developer)\b",
        from_snip,
        re.I,
    ):
        return from_snip.title() if from_snip.islower() else from_snip

    # Last resort: first chunk of subject
    sub = re.sub(r"^(re|fw|fwd):\s*", "", (subject or "").strip(), flags=re.I)
    chunk = sub.split("-")[0].split("|")[0].split("—")[0].strip()
    if chunk and not re.search(r"thank|appl(y|ication)|received", chunk, re.I):
        return _clean_company(chunk)[:80]
    return "Unknown"


def extract_role_guess(subject: str, snippet: str = "") -> str:
    blob = f"{subject} {snippet}"
    patterns = [
        r"(?:position(?: of)?|role(?: of)?|for(?: the)?)\s*[:\-]?\s*([A-Z][^.\n!]{5,90}?)(?:\s+at\s+|\s*[.!]|$)",
        r"(Summer\s+20\d{2}[^.\n!]{0,80}Intern[^.\n!]{0,40})",
        r"(Fall\s+20\d{2}[^.\n!]{0,80}(?:Intern|Co-?op)[^.\n!]{0,40})",
        r"((?:Software|Data|Machine Learning|AI|ML|TPM|Product|DevOps)[^.\n!]{0,60}Intern(?:ship)?[^.\n!]{0,40})",
    ]
    for pat in patterns:
        m = re.search(pat, blob, flags=re.I)
        if m:
            role = re.sub(r"\s+", " ", m.group(1)).strip(" -:|")
            role = re.sub(r"\s+Our Recruiting.*$", "", role, flags=re.I)
            if 3 < len(role) < 120:
                return role[:120]
    # Intuit-style subject: "... applying to the Summer 2027: Mobile ... Role at Intuit"
    m = re.search(r"applying to the\s+(.+?)\s+Role at\s+", subject or "", flags=re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()[:120]
    return "(role not in email)"


def classify_role_family(role: str) -> str:
    blob = f" { (role or '').lower() } "
    for family, needles in ROLE_FAMILY_RULES:
        if any(n in blob for n in needles):
            return family
    return "Other"


def tier_display(company: str) -> str:
    raw = classify_company_tier(company)
    return {"priority": "Priority", "fortune500": "Fortune500", "other": "Other"}.get(raw, "Other")


def _load_creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    tp = token_path()
    if tp.is_file():
        creds = Credentials.from_authorized_user_file(str(tp), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not secrets_path().is_file():
                raise FileNotFoundError(
                    f"Missing {secrets_path()}. See docs/ACCOUNTS.md (Gmail desktop OAuth)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path()), SCOPES)
            creds = flow.run_local_server(port=0)
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text(creds.to_json())
    return creds


def _service():
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=_load_creds(), cache_discovery=False)


def ensure_labels(service) -> dict[str, str]:
    """Ensure JobRadar parent + nested status labels. Returns map status→id."""
    existing = {x["name"]: x["id"] for x in service.users().labels().list(userId="me").execute().get("labels", [])}
    ids: dict[str, str] = {}

    if LABEL_PREFIX not in existing:
        created = service.users().labels().create(
            userId="me",
            body={
                "name": LABEL_PREFIX,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        ).execute()
        existing[LABEL_PREFIX] = created["id"]
    ids["_parent"] = existing[LABEL_PREFIX]

    for status in STATUS_LABELS:
        full = nested_label_name(status)
        if full in existing:
            ids[status] = existing[full]
            continue
        created = service.users().labels().create(
            userId="me",
            body={
                "name": full,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        ).execute()
        ids[status] = created["id"]
        existing[full] = created["id"]
    return ids


def legacy_label_ids(service) -> list[str]:
    existing = {x["name"]: x["id"] for x in service.users().labels().list(userId="me").execute().get("labels", [])}
    return [existing[name] for name in LEGACY_FLAT_LABELS if name in existing]


# Higher rank wins when a thread has mixed signals across messages.
STATUS_RANK: dict[str, int] = {
    "Backlog": 0,
    "Waiting": 1,
    "Recruiter": 2,
    "Applied": 3,
    "OA": 4,
    "Interview": 5,
    "Final Round": 6,
    "Offer": 7,
    "Ghosted": 8,
    "Rejected": 9,
}


def status_from_classification(classification: str) -> str | None:
    status = STATUS_FOR.get(classification, "")
    if status in STATUS_LABELS:
        return status
    return None


def _other_nested_status_ids(label_ids: dict[str, str], keep: str | None) -> list[str]:
    return [label_ids[s] for s in STATUS_LABELS if s in label_ids and s != keep]


def apply_thread_status(
    service,
    thread_id: str,
    status: str | None,
    label_ids: dict[str, str],
    legacy_ids: list[str],
) -> None:
    """Ensure JobRadar parent + one nested status; strip legacy flat labels."""
    add_ids = [label_ids["_parent"]]
    if status and status in label_ids:
        add_ids.append(label_ids[status])
    remove_ids = list(legacy_ids) + _other_nested_status_ids(label_ids, status)
    remove_ids = [x for x in remove_ids if x not in add_ids]
    if not add_ids and not remove_ids:
        return
    body: dict = {}
    if add_ids:
        body["addLabelIds"] = add_ids
    if remove_ids:
        body["removeLabelIds"] = remove_ids
    service.users().threads().modify(userId="me", id=thread_id, body=body).execute()


def _job_search_query(*, days: int) -> str:
    return (
        f"newer_than:{days}d "
        "(subject:(appl OR interview OR assessment OR offer OR unfortunately OR recruiter OR hackerrank OR codesignal OR phone screen) "
        "OR from:(greenhouse OR lever OR ashby OR workday OR icims OR handshake OR myworkday OR recruiting OR careers OR no-reply OR noreply) "
        "OR label:JobRadar OR label:Applied OR label:\"Job Oriented\" OR label:\"JobRadar/Applied\")"
    )


def reorganize(
    db: Database | None = None,
    *,
    days: int = 365,
    max_threads: int = 500,
    dry_run: bool = False,
) -> dict:
    """Backfill: classify job threads, apply exclusive nested JobRadar/* labels, optional Notion sync."""
    from jobradar import notion as notion_mod

    if not configured():
        return {"skipped": True, "reason": "no gmail-client.json"}
    service = _service()
    label_ids = ensure_labels(service)
    legacy_ids = legacy_label_ids(service)
    q = _job_search_query(days=days)
    resp = service.users().threads().list(userId="me", q=q, maxResults=max_threads).execute()
    threads = resp.get("threads") or []
    stats = {
        "threads": len(threads),
        "labeled": 0,
        "skipped_other": 0,
        "notion": 0,
        "dry_run": dry_run,
    }
    if db is None:
        db = Database()

    for meta in threads:
        tid = meta["id"]
        thread = service.users().threads().get(
            userId="me",
            id=tid,
            format="metadata",
            metadataHeaders=["Subject", "From"],
        ).execute()
        messages = thread.get("messages") or []
        if not messages:
            continue

        best_class = "other"
        best_rank = -1
        latest_subject = ""
        latest_from = ""
        latest_snippet = ""
        for msg in messages:
            headers = msg.get("payload", {}).get("headers") or []
            subject = _header(headers, "Subject")
            from_addr = _header(headers, "From")
            snippet = msg.get("snippet") or ""
            classification = classify_email(subject, snippet, from_addr)
            latest_subject, latest_from, latest_snippet = subject, from_addr, snippet
            status = status_from_classification(classification)
            if status:
                rank = STATUS_RANK.get(status, 0)
                if rank > best_rank:
                    best_rank = rank
                    best_class = classification

        status = status_from_classification(best_class)
        if not status:
            stats["skipped_other"] += 1
            if not dry_run:
                apply_thread_status(service, tid, None, label_ids, legacy_ids)
            continue

        if dry_run:
            stats["labeled"] += 1
            continue

        apply_thread_status(service, tid, status, label_ids, legacy_ids)
        stats["labeled"] += 1

        company = extract_company_guess(latest_subject, latest_from, latest_snippet)
        role = extract_role_guess(latest_subject, latest_snippet)
        gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{tid}"
        job = db.find_job_by_company(company)
        if job:
            canonical = job.canonical_key
            title = job.title
            company = job.company
            location = job.location
            url = job.url
            priority = job.priority
            sources = list(job.sources)
            posted_at = job.posted_at or ""
            first_seen = job.first_seen_at
            last_seen = job.last_seen_at
        else:
            canonical = _email_canonical_key(company, role, tid)
            title = role
            location = url = posted_at = ""
            priority = classify_company_tier(company) == "priority"
            sources = ["gmail"]
            now = datetime.now(timezone.utc).isoformat()
            first_seen = last_seen = now

        date_applied = datetime.now(timezone.utc).isoformat() if status == "Applied" else ""
        db.upsert_application(
            canonical_key=canonical,
            company=company,
            title=title,
            status=status,
            date_applied=date_applied or None,
            gmail_thread_id=gmail_url,
        )
        record = JobRecord(
            canonical_key=canonical,
            company=company,
            title=title,
            location=location,
            url=url,
            sources=sources,
            priority=priority,
            first_seen_at=first_seen or datetime.now(timezone.utc).isoformat(),
            last_seen_at=last_seen or datetime.now(timezone.utc).isoformat(),
            posted_at=posted_at,
        )
        try:
            if notion_mod.upsert_job(
                record,
                db=db,
                status=status,
                gmail_thread=gmail_url,
                role_family=classify_role_family(title),
                tier=tier_display(company),
                date_applied=date_applied,
            ):
                stats["notion"] += 1
        except Exception as exc:
            log.warning("notion from reorganize failed: %s", exc)
    return stats


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value") or ""
    return ""


def auth() -> str:
    _load_creds()
    return f"ok token={token_path()}"


def _email_canonical_key(company: str, role: str, thread_id: str) -> str:
    base = f"gmail:{company}:{role}:{thread_id}".lower()
    base = re.sub(r"[^a-z0-9:._-]+", "-", base)
    return base[:200]


def sync(db: Database, *, days: int = 7, max_results: int = 100) -> dict:
    """Fetch recent mail, classify, label under JobRadar/*, patch applications + Notion."""
    from jobradar import notion as notion_mod

    if not configured():
        return {"skipped": True, "reason": "no gmail-client.json"}
    service = _service()
    label_ids = ensure_labels(service)
    remove_ids = legacy_label_ids(service)
    q = f"newer_than:{days}d (subject:(appl OR interview OR assessment OR offer OR unfortunately OR recruiter OR hackerrank OR codesignal) OR from:(greenhouse OR lever OR ashby OR workday OR icims OR recruiting OR careers OR no-reply OR noreply))"
    resp = service.users().messages().list(userId="me", q=q, maxResults=max_results).execute()
    messages = resp.get("messages") or []
    stats = {"fetched": len(messages), "new": 0, "labeled": 0, "matched": 0, "notion": 0}
    for meta in messages:
        mid = meta["id"]
        msg = service.users().messages().get(
            userId="me",
            id=mid,
            format="metadata",
            metadataHeaders=["Subject", "From"],
        ).execute()
        headers = msg.get("payload", {}).get("headers") or []
        subject = _header(headers, "Subject")
        from_addr = _header(headers, "From")
        snippet = msg.get("snippet") or ""
        thread_id = msg.get("threadId") or ""
        classification = classify_email(subject, snippet, from_addr)
        inserted = db.record_email(
            message_id=mid,
            thread_id=thread_id,
            subject=subject,
            from_addr=from_addr,
            classification=classification,
        )
        if not inserted:
            continue
        stats["new"] += 1

        status = status_from_classification(classification)
        try:
            apply_thread_status(service, thread_id, status, label_ids, remove_ids)
            stats["labeled"] += 1
        except Exception as exc:
            log.warning("gmail label failed: %s", exc)

        if not status:
            continue

        company = extract_company_guess(subject, from_addr, snippet)
        role = extract_role_guess(subject, snippet)
        gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"
        job = db.find_job_by_company(company)
        if job:
            stats["matched"] += 1
            canonical = job.canonical_key
            title = job.title
            company = job.company
            location = job.location
            url = job.url
            priority = job.priority
            sources = list(job.sources)
            posted_at = job.posted_at or ""
            first_seen = job.first_seen_at
            last_seen = job.last_seen_at
        else:
            canonical = _email_canonical_key(company, role, thread_id)
            title = role
            location = ""
            url = ""
            priority = classify_company_tier(company) == "priority"
            sources = ["gmail"]
            posted_at = ""
            now = datetime.now(timezone.utc).isoformat()
            first_seen = now
            last_seen = now

        date_applied = ""
        if classification == "applied":
            date_applied = datetime.now(timezone.utc).isoformat()

        db.upsert_application(
            canonical_key=canonical,
            company=company,
            title=title,
            status=status,
            date_applied=date_applied or None,
            gmail_thread_id=gmail_url,
        )

        record = JobRecord(
            canonical_key=canonical,
            company=company,
            title=title,
            location=location,
            url=url,
            sources=sources,
            priority=priority,
            first_seen_at=first_seen or datetime.now(timezone.utc).isoformat(),
            last_seen_at=last_seen or datetime.now(timezone.utc).isoformat(),
            posted_at=posted_at,
        )
        try:
            page_id = notion_mod.upsert_job(
                record,
                db=db,
                status=status,
                gmail_thread=gmail_url,
                role_family=classify_role_family(title),
                tier=tier_display(company),
                date_applied=date_applied,
            )
            if page_id:
                stats["notion"] += 1
        except Exception as exc:
            log.warning("notion from gmail failed: %s", exc)
    return stats
