"""Recall-first job classification rules."""

from __future__ import annotations

from jobradar.models import JobRecord

INCLUDE = (
    "software", "swe", "sde", "engineer", "engineering", "developer", "devops",
    "data science", "data scientist", "data engineer", "analytics", "analyst",
    "machine learning", "ml ", " ml", "artificial intelligence", " ai", "ai ",
    "research", "quant", "infrastructure", "backend", "frontend", "full stack",
    "fullstack", "platform", "systems", "security", "robotics", "applied ai",
    "mle", "deeplearning", "deep learning", "nlp", "computer vision",
)

EXCLUDE = (
    "nursing", "nurse", "tax intern", "tax analyst", "accounting intern",
    "pharmacist", "dental", "medical assistant", "registered nurse",
    "social work", "hr intern", "human resources", "recruiter intern",
    "marketing intern", "sales intern", "real estate",
)

PRIORITY_COMPANIES = {
    "openai", "anthropic", "databricks", "snowflake", "nvidia", "scale ai",
    "perplexity", "meta", "google", "microsoft", "apple", "tesla", "palantir",
    "stripe", "figma", "roblox", "netflix", "jane street", "hudson river trading",
    "citadel", "ramp", "cursor", "anduril", "xai",
}


def _blob(job: JobRecord) -> str:
    return f"{job.company} {job.title} {job.snippet}".lower()


def should_keep(job: JobRecord) -> bool:
    text = _blob(job)
    if any(x in text for x in EXCLUDE):
        # still keep if strong include signal (e.g. "tax" false positive in other context)
        if any(x in text for x in ("software", "engineer", "machine learning", "data science")):
            return True
        return False
    if any(x in text for x in INCLUDE):
        return True
    # recall-first: keep unknown rather than drop
    return True


def is_priority_company(company: str) -> bool:
    c = (company or "").strip().lower()
    if c in PRIORITY_COMPANIES:
        return True
    return any(p in c for p in PRIORITY_COMPANIES)


def enrich(job: JobRecord) -> JobRecord:
    if is_priority_company(job.company):
        job.priority = True
    return job
