"""Gmail classify + label. Rules first. Never used as an alert channel."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from jobradar.db import Database

log = logging.getLogger("jobradar.gmail")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

LABELS = ("Applied", "Interview", "OA", "Rejected", "Offer", "Recruiter", "Waiting")

STATUS_FOR = {
    "applied": "Applied",
    "interview": "Interview",
    "oa": "OA",
    "rejected": "Rejected",
    "offer": "Offer",
    "recruiter": "Recruiter",
    "waiting": "Waiting",
    "other": "Seen",
}

RULES: list[tuple[str, tuple[str, ...]]] = [
    ("rejected", ("unfortunately", "not moving forward", "other candidates", "we regret", "will not be moving")),
    ("offer", ("offer letter", "pleased to offer", "congratulations on your offer")),
    ("oa", ("hackerrank", "codesignal", "codility", "online assessment", "oa invite", "coding assessment")),
    ("interview", ("interview", "phone screen", "phone-screen", "schedule a call", "virtual onsite")),
    ("applied", ("thanks for applying", "thank you for applying", "we received your application", "application received")),
    ("recruiter", ("talent acquisition", "i'd like to connect", "reaching out about", "recruiting team")),
    ("waiting", ("under review", "still reviewing", "application is being reviewed")),
]


def secrets_path() -> Path:
    return Path(os.environ.get("GMAIL_CLIENT_SECRETS", "secrets/gmail-client.json"))


def token_path() -> Path:
    return Path(os.environ.get("GMAIL_TOKEN", "secrets/gmail-token.json"))


def configured() -> bool:
    return secrets_path().is_file()


def classify_email(subject: str, snippet: str = "", from_addr: str = "") -> str:
    blob = f"{subject} {snippet} {from_addr}".lower()
    for label, needles in RULES:
        if any(n in blob for n in needles):
            return label
    if "greenhouse" in blob or "lever.co" in blob or "ashbyhq" in blob:
        return "applied"
    return "other"


def extract_company_guess(subject: str, from_addr: str) -> str:
    m = re.search(r"@([a-z0-9.-]+)\.", (from_addr or "").lower())
    if m:
        host = m.group(1)
        host = host.replace("mail.", "").replace("email.", "").replace("jobs.", "")
        part = host.split(".")[-1] if "." in host else host
        if part not in {"gmail", "googlemail", "outlook", "yahoo", "icloud", "hotmail"}:
            return part.replace("-", " ")
    sub = (subject or "").strip()
    sub = re.sub(r"^(re|fw|fwd):\s*", "", sub, flags=re.I)
    return sub.split("-")[0].split("|")[0].strip()[:80]


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
    existing = {x["name"]: x["id"] for x in service.users().labels().list(userId="me").execute().get("labels", [])}
    ids = {}
    for name in LABELS:
        if name in existing:
            ids[name] = existing[name]
            continue
        created = service.users().labels().create(
            userId="me",
            body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        ).execute()
        ids[name] = created["id"]
    return ids


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value") or ""
    return ""


def auth() -> str:
    _load_creds()
    return f"ok token={token_path()}"


def sync(db: Database, *, days: int = 7, max_results: int = 100) -> dict:
    """Fetch recent mail, classify, label, patch applications + Notion."""
    from jobradar import notion as notion_mod

    if not configured():
        return {"skipped": True, "reason": "no gmail-client.json"}
    service = _service()
    label_ids = ensure_labels(service)
    q = f"newer_than:{days}d"
    resp = service.users().messages().list(userId="me", q=q, maxResults=max_results).execute()
    messages = resp.get("messages") or []
    stats = {"fetched": len(messages), "new": 0, "labeled": 0, "matched": 0}
    for meta in messages:
        mid = meta["id"]
        msg = service.users().messages().get(userId="me", id=mid, format="metadata", metadataHeaders=["Subject", "From"]).execute()
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
        label_name = STATUS_FOR.get(classification, "")
        if classification != "other" and label_name in label_ids:
            try:
                service.users().messages().modify(
                    userId="me",
                    id=mid,
                    body={"addLabelIds": [label_ids[label_name]]},
                ).execute()
                stats["labeled"] += 1
            except Exception as exc:
                log.warning("gmail label failed: %s", exc)
        guess = extract_company_guess(subject, from_addr)
        job = db.find_job_by_company(guess)
        gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"
        if job:
            stats["matched"] += 1
            status = STATUS_FOR.get(classification, "Seen")
            if classification == "applied":
                from datetime import datetime, timezone

                db.upsert_application(
                    canonical_key=job.canonical_key,
                    company=job.company,
                    title=job.title,
                    status=status,
                    date_applied=datetime.now(timezone.utc).isoformat(),
                    gmail_thread_id=gmail_url,
                )
            else:
                db.upsert_application(
                    canonical_key=job.canonical_key,
                    company=job.company,
                    title=job.title,
                    status=status,
                    gmail_thread_id=gmail_url,
                )
            try:
                notion_mod.upsert_job(job, db=db, status=status, gmail_thread=gmail_url)
            except Exception as exc:
                log.warning("notion from gmail failed: %s", exc)
    return stats
