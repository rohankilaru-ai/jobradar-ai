"""Source catalog for JobRadar scouts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    kind: str  # aprameyak | dreamwork | applyguy | simplify


SOURCES: list[Source] = [
    Source(
        name="aprameyak-2027",
        url="https://raw.githubusercontent.com/aprameyak/2027-tech-jobs/main/listings.json",
        kind="aprameyak",
    ),
    Source(
        name="dreamwork-2027",
        url="https://raw.githubusercontent.com/dreamworkhq/Tech-Internships-2027/main/data/listings.json",
        kind="dreamwork",
    ),
    Source(
        name="applyguy-2027",
        url="https://raw.githubusercontent.com/ApplyGuy/2027-Internships/main/data/internships.json",
        kind="applyguy",
    ),
    Source(
        name="simplify-summer-2027",
        url="https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README.md",
        kind="simplify",
    ),
    Source(
        name="simplify-offseason-2027",
        url="https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README-Off-Season.md",
        kind="simplify",
    ),
    # Disabled: Rohan targets internships only, not new-grad roles
    # Source(
    #     name="simplify-newgrad",
    #     url="https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md",
    #     kind="simplify",
    # ),
    Source(
        name="vansh-summer-2027",
        url="https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/README.md",
        kind="markdown",
    ),
    Source(
        name="speedyapply-swe-2027",
        url="https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md",
        kind="markdown",
    ),
    Source(
        name="speedyapply-swe-intl-2027",
        url="https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/INTERN_INTL.md",
        kind="markdown",
    ),
    Source(
        name="speedyapply-ai-2027",
        url="https://raw.githubusercontent.com/speedyapply/2027-AI-College-Jobs/main/README.md",
        kind="markdown",
    ),
    Source(
        name="speedyapply-ai-intl-2027",
        url="https://raw.githubusercontent.com/speedyapply/2027-AI-College-Jobs/main/INTERN_INTL.md",
        kind="markdown",
    ),
]
