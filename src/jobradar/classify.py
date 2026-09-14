"""Recall-first job classification rules.

The exclude list targets common false positives from internship boards:
- Medical/healthcare: nursing, clinical, pharmacy, dental, etc.
- Finance/accounting (non-technical): tax, bookkeeping, payroll, etc.
- Legal: paralegal, law clerk, legal assistant, etc.
- HR/recruiting/admin: human resources, recruiter, receptionist, etc.
- Sales/marketing (non-technical): sales rep, account executive, business dev, etc.
- Content/media (non-technical): copywriter, journalist, PR, etc.
- Operations/logistics (non-technical): warehouse, inventory, supply chain, etc.
- Service/hospitality: customer service, retail, cashier, etc.
- Education: teaching, tutoring, camp counselor, etc.
- Arts/design (non-technical): graphic design, photography, videography, etc.

Strong include signals (software, engineer, ML, data science) override exclude matches
to prevent false negatives on edge cases like "Software Tax Engineer".
"""

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
    # Medical/healthcare roles
    "nursing", "nurse", "pharmacist", "dental", "medical assistant", 
    "registered nurse", "physician", "clinical", "healthcare",
    # Finance/accounting (non-technical)
    "tax intern", "tax analyst", "tax accountant", "accounting intern", 
    "accountant", "bookkeeper", "accounts payable", "accounts receivable", "payroll",
    # Legal
    "legal intern", "paralegal", "law clerk", "legal assistant",
    # HR/recruiting/admin
    "social work", "hr intern", "human resources", "recruiter intern",
    "administrative assistant", "office assistant", "receptionist",
    # Sales/marketing/business development (non-technical)
    "marketing intern", "sales intern", "real estate", "business development intern",
    "account executive intern", "sales rep", "sales associate",
    # Content/media (non-technical)
    "content writer", "copywriter", "journalist", "editorial intern",
    "communications intern", "public relations", "pr intern",
    # Operations/logistics (non-technical)
    "warehouse", "logistics intern", "supply chain intern", "operations intern",
    "inventory", "driver",
    # Service/hospitality
    "customer service intern", "retail", "cashier", "server", "host",
    # Education/tutoring
    "teacher", "tutor", "teaching assistant", "camp counselor",
    # Arts/design (non-technical)
    "graphic design intern", "photographer", "videographer", "artist",
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
