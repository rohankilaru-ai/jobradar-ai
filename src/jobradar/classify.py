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
    "nursing", "nurse", "pharmacist", "pharmacy tech", "dental", "medical assistant", 
    "registered nurse", "physician", "clinical", "healthcare", "therapist", "physical therapy",
    "occupational therapy", "medical scribe", "patient care",
    # Finance/accounting (non-technical)
    "tax intern", "tax analyst", "tax accountant", "tax preparer", "accounting intern", 
    "accountant", "bookkeeper", "accounts payable", "accounts receivable", "payroll",
    "audit intern", "auditor", "financial advisor", "wealth management", "personal banker",
    "investment banking analyst", "private equity analyst", "credit analyst",
    # Legal
    "legal intern", "paralegal", "law clerk", "legal assistant", "compliance intern",
    "legal operations",
    # HR/recruiting/admin
    "social work", "hr intern", "human resources", "recruiter intern", "recruiting coordinator",
    "administrative assistant", "office assistant", "receptionist", "office manager",
    "executive assistant",
    # Sales/marketing/business development (non-technical)
    "marketing intern", "sales intern", "real estate", "business development intern",
    "account executive intern", "sales rep", "sales associate", "sales development",
    "account manager intern", "customer success intern", "partnership intern",
    "growth marketing intern", "brand marketing", "product marketing intern",
    # Content/media (non-technical)
    "content writer", "copywriter", "journalist", "editorial intern", "editor",
    "communications intern", "public relations", "pr intern", "social media intern",
    "media producer", "content creator",
    # Operations/logistics/supply chain (non-technical)
    "warehouse", "logistics intern", "supply chain intern", "operations intern",
    "inventory", "driver", "business operations intern", "program coordinator",
    "project coordinator intern", "operations coordinator",
    # Service/hospitality
    "customer service intern", "retail", "cashier", "server", "host", "barista",
    "front desk", "concierge",
    # Education/tutoring
    "teacher", "tutor", "teaching assistant", "camp counselor", "instructor",
    # Arts/design (non-technical)
    "graphic design intern", "photographer", "videographer", "artist", "illustrator",
    "ux designer intern", "ui designer intern", "visual designer",
    # Construction/trades/manual labor
    "construction", "electrician", "plumber", "mechanic", "maintenance", "technician intern",
    "hvac", "welder", "carpenter",
    # Insurance
    "insurance intern", "claims adjuster", "underwriter intern",
    # Consulting (non-technical management consulting)
    "management consulting intern", "strategy consulting intern", "business consultant intern",
)

# New-grad / full-time signals (exclude unless also clearly an intern role)
NEWGRAD_SIGNALS = (
    "new grad", "new-grad", "newgrad", "new graduate", "recent graduate",
    "university graduate", "college graduate", "full-time", "full time",
    "entry level", "entry-level", "early career", "early careers",
    "early-career", "university grad", "grad program", "new graduate engineer",
)

# PhD / Masters / post-grad — hard exclude even when title also says Intern
# (Rohan is undergrad; these pings are noise.)
GRAD_LEVEL_SIGNALS = (
    "phd", "ph.d", "ph.d.", "doctoral", "doctorate",
    "master's", "masters ", " masters", "mba ",
    "post-grad", "postgrad", "post graduate", "postgraduate", "postdoc", "post-doc",
    "graduate student", "grad student",
    " - ms", " – ms", " — ms", "(ms)", " ms,", " ms ",
    "ms only", "ms/phd", "phd/ms",
    "🎓",
)

# Intern signals that override new-grad exclusion (NOT grad-level exclusion)
INTERN_SIGNALS = (
    "intern", "internship", "co-op", "coop", "summer", "spring", "fall", "winter",
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

    # Hard-drop PhD / Masters / post-grad (including "Intern - MS/PhD")
    if any(x in text for x in GRAD_LEVEL_SIGNALS):
        # Allow explicit undergrad dual-track like "BS/MS" only when PhD is absent
        if "phd" in text or "ph.d" in text or "doctoral" in text or "doctorate" in text:
            return False
        # Allow undergrad-eligible dual listings (BS/MS, BS / MS, B.S./M.S, etc.)
        if any(pattern in text for pattern in ("bs/ms", "bs / ms", "b.s./m.s", "b.s. / m.s.",
                                                "bachelor/master", "bachelor / master",
                                                "bachelor's/master's", "bachelor's / master's")):
            pass  # undergrad-eligible dual listing
        else:
            return False

    # Check for new-grad / full-time signals
    has_newgrad = any(x in text for x in NEWGRAD_SIGNALS)
    has_intern = any(x in text for x in INTERN_SIGNALS)

    # Exclude new-grad roles unless they're also clearly internships
    if has_newgrad and not has_intern:
        return False
    
    # Check exclude list
    if any(x in text for x in EXCLUDE):
        # Strong technical signals override exclude matches (e.g. "Tax Software Engineer")
        # This prevents false negatives on edge cases where exclude keywords appear
        # in otherwise-valid technical roles
        strong_signals = (
            "software", "swe ", " swe", "engineer", "engineering", "developer", 
            "machine learning", "data science", "data scientist", "data engineer",
            " ml ", " ai ", "artificial intelligence", "devops", "backend", "frontend",
            "full stack", "fullstack", "platform engineer", "systems engineer",
            "quant", "infrastructure engineer",
        )
        if any(sig in text for sig in strong_signals):
            return True
        return False
    
    # Positive technical signals
    if any(x in text for x in INCLUDE):
        return True
    
    # Recall-first: unknown roles default to keep (false positives OK, missed jobs not OK)
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
