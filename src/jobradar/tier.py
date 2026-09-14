"""Company tier classification for Discord alert routing.

Three tiers:
- Priority: Strategic high-value employers (OpenAI, Anthropic, etc.)
- Fortune500: Large established employers not in Priority
- Other: Everything else

Fuzzy matching normalizes company names (case, punctuation, common suffixes).
"""

from __future__ import annotations

import re

# Priority companies (Strategist-approved list)
PRIORITY_COMPANIES = {
    "openai",
    "anthropic",
    "databricks",
    "snowflake",
    "nvidia",
    "scale ai",
    "perplexity",
    "meta",
    "facebook",  # alias for Meta
    "google",
    "microsoft",
    "apple",
    "tesla",
    "palantir",
    "stripe",
    "figma",
    "roblox",
    "netflix",
    "jane street",
    "hudson river trading",
    "citadel",
    "ramp",
    "cursor",
    "anduril",
    "xai",
}

# Fortune500-tier companies (large employers not in Priority)
# This is a maintainable list Rohan can edit
FORTUNE500_COMPANIES = {
    # Banks & Financial Services
    "jpmorgan chase",
    "jpmorgan",
    "jp morgan",
    "bank of america",
    "wells fargo",
    "citigroup",
    "citi",
    "goldman sachs",
    "goldman sachs group",
    "morgan stanley",
    "charles schwab",
    "american express",
    "amex",
    "capital one",
    "us bank",
    "pnc bank",
    "pnc financial",
    "td bank",
    "truist",
    "fifth third",
    "ally financial",
    "discover",
    "synchrony",
    "state street",
    "bny mellon",
    "blackrock",
    "vanguard",
    "fidelity",
    "t rowe price",
    "franklin templeton",
    
    # Insurance
    "berkshire hathaway",
    "unitedhealth",
    "united healthcare",
    "anthem",
    "elevance",
    "cigna",
    "humana",
    "centene",
    "aetna",
    "kaiser permanente",
    "progressive",
    "allstate",
    "travelers",
    "liberty mutual",
    "nationwide",
    "state farm",
    "usaa",
    "metlife",
    "prudential",
    "aflac",
    "chubb",
    "marsh mclennan",
    "aon",
    "willis towers watson",
    
    # Retail & Consumer
    "walmart",
    "amazon",  # not in priority, but could be added if desired
    "costco",
    "kroger",
    "walgreens",
    "cvs health",
    "cvs",
    "target",
    "home depot",
    "lowes",
    "best buy",
    "macys",
    "kohls",
    "nordstrom",
    "tjx",
    "tj maxx",
    "ross stores",
    "dollar general",
    "dollar tree",
    
    # Tech (not Priority)
    "ibm",
    "oracle",
    "salesforce",
    "adobe",
    "intuit",
    "servicenow",
    "vmware",
    "dell",
    "hp inc",
    "hewlett packard",
    "cisco",
    "intel",
    "amd",
    "qualcomm",
    "broadcom",
    "texas instruments",
    "micron",
    "western digital",
    "seagate",
    "netapp",
    "workday",
    "atlassian",
    "uber",
    "lyft",
    "airbnb",
    "doordash",
    "instacart",
    "snap",
    "snapchat",
    "pinterest",
    "reddit",
    "discord",
    "twitch",
    "spotify",
    "zoom",
    "slack",
    "dropbox",
    "box",
    "docusign",
    "hubspot",
    "zendesk",
    "shopify",
    "square",
    "block",
    "paypal",
    "coinbase",
    
    # Telecom & Media
    "att",
    "at t",
    "at&t",
    "verizon",
    "t mobile",
    "tmobile",
    "comcast",
    "charter",
    "spectrum",
    "dish network",
    "directv",
    "disney",
    "comcast nbcuniversal",
    "nbcuniversal",
    "paramount",
    "cbs",
    "warner bros",
    "discovery",
    "sony",
    "fox corporation",
    "new york times",
    "washington post",
    "thomson reuters",
    "bloomberg",
    
    # Aerospace & Defense
    "lockheed martin",
    "boeing",
    "raytheon",
    "northrop grumman",
    "general dynamics",
    "l3harris",
    "leidos",
    "bae systems",
    "textron",
    
    # Automotive
    "general motors",
    "gm",
    "ford",
    "stellantis",
    "chrysler",
    "fiat",
    "toyota",
    "honda",
    "nissan",
    "volkswagen",
    "bmw",
    "mercedes",
    "daimler",
    "hyundai",
    "kia",
    "mazda",
    "subaru",
    
    # Industrial & Manufacturing
    "ge",
    "general electric",
    "3m",
    "caterpillar",
    "deere",
    "john deere",
    "honeywell",
    "emerson",
    "parker hannifin",
    "eaton",
    "cummins",
    "paccar",
    "dover",
    "xylem",
    "itt",
    
    # Energy & Utilities
    "exxonmobil",
    "exxon",
    "mobil",
    "chevron",
    "conocophillips",
    "marathon petroleum",
    "valero",
    "phillips 66",
    "enterprise products",
    "shell",
    "bp",
    "total",
    "equinor",
    "duke energy",
    "southern company",
    "nextera",
    "dominion",
    "exelon",
    "american electric power",
    "pge",
    "pg&e",
    "sempra",
    "consolidated edison",
    
    # Pharma & Healthcare
    "johnson johnson",
    "johnson & johnson",
    "pfizer",
    "merck",
    "abbvie",
    "bristol myers squibb",
    "eli lilly",
    "amgen",
    "gilead",
    "regeneron",
    "biogen",
    "vertex",
    "moderna",
    "biontech",
    "mckesson",
    "cardinal health",
    "amerisourcebergen",
    "hca healthcare",
    "tenet",
    "universal health services",
    "quest diagnostics",
    "labcorp",
    "davita",
    "fresenius",
    
    # Food & Beverage
    "pepsico",
    "coca cola",
    "mondelez",
    "kraft heinz",
    "general mills",
    "kellogg",
    "conagra",
    "tyson",
    "hormel",
    "campbell",
    "mars",
    "hershey",
    "starbucks",
    "mcdonalds",
    "yum brands",
    "chipotle",
    "dominos",
    "restaurant brands",
    
    # Consulting & Services
    "accenture",
    "deloitte",
    "pwc",
    "pricewaterhousecoopers",
    "ey",
    "ernst & young",
    "kpmg",
    "mckinsey",
    "bain",
    "bcg",
    "boston consulting group",
    "booz allen",
    "cognizant",
    "infosys",
    "tata consultancy",
    "tcs",
    "wipro",
    "capgemini",
    
    # Other Notable
    "fedex",
    "ups",
    "united parcel service",
    "usps",
    "us postal service",
    "jb hunt",
    "xpo logistics",
    "schneider",
    "hilton",
    "marriott",
    "hyatt",
    "intercontinental",
    "mgm",
    "caesars",
    "wynn",
    "las vegas sands",
}


def _normalize_company(company: str) -> str:
    """Normalize company name for matching.
    
    - Lowercase
    - Remove common suffixes (inc, corp, ltd, etc.)
    - Remove punctuation and extra whitespace
    """
    if not company:
        return ""
    
    name = company.lower().strip()
    
    # Replace & and - with space before removing punctuation
    name = name.replace("&", " ").replace("-", " ")
    
    # Remove common suffixes (multiple passes to handle "Group Inc." etc.)
    suffixes = [
        " inc",
        " inc.",
        " incorporated",
        " llc",
        " l.l.c.",
        " corp",
        " corp.",
        " corporation",
        " ltd",
        " ltd.",
        " limited",
        " company",
        " co",
        " co.",
        " plc",
        " group",
    ]
    
    # Multiple passes to handle compound suffixes like "Group Inc."
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
                changed = True
    
    # Remove punctuation but preserve spaces
    name = re.sub(r"[^\w\s]", "", name)
    
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name).strip()
    
    return name


def classify_company_tier(company: str) -> str:
    """Classify company into tier: 'priority', 'fortune500', or 'other'.
    
    Uses fuzzy/normalized matching on company name.
    
    Args:
        company: Company name from JobRecord
    
    Returns:
        One of: 'priority', 'fortune500', 'other'
    """
    if not company:
        return "other"
    
    normalized = _normalize_company(company)
    
    # Check Priority tier first (most specific)
    if normalized in PRIORITY_COMPANIES:
        return "priority"
    
    # Check for common aliases/variations
    # Meta/Facebook
    if "meta" in normalized or "facebook" in normalized:
        return "priority"
    
    # NVIDIA variations
    if "nvidia" in normalized or "nvda" in normalized:
        return "priority"
    
    # xAI variations
    if normalized in ("xai", "x ai"):
        return "priority"
    
    # Check Fortune500 tier
    if normalized in FORTUNE500_COMPANIES:
        return "fortune500"
    
    # Default to Other
    return "other"
