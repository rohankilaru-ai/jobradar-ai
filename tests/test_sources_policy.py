"""Tests for sources policy and standing bans."""

import pytest

from jobradar.sources import SOURCES


def test_pittcsc_summer2027_banned():
    """
    REGRESSION TEST: pittcsc/Summer2027-Internships must NEVER be in default SOURCES.
    
    Standing ban: Rohan has explicitly banned this source from JobRadar.
    If this test fails, a source was accidentally added that violates the policy.
    """
    # Check that no source URL contains pittcsc/Summer2027-Internships
    pittcsc_urls = [
        s.url for s in SOURCES
        if "pittcsc" in s.url.lower() and "summer2027" in s.url.lower()
    ]
    
    assert len(pittcsc_urls) == 0, (
        f"POLICY VIOLATION: pittcsc/Summer2027-Internships is banned but found in SOURCES: {pittcsc_urls}"
    )


def test_no_pittcsc_in_any_form():
    """Ensure pittcsc is not in SOURCES in any form (summer/offseason)."""
    pittcsc_sources = [s for s in SOURCES if "pittcsc" in s.url.lower()]
    
    assert len(pittcsc_sources) == 0, (
        f"POLICY VIOLATION: pittcsc sources are banned but found: {[s.url for s in pittcsc_sources]}"
    )


def test_sources_are_internship_focused():
    """
    Verify SOURCES contains only internship-focused repos.
    
    Allowed patterns:
    - aprameyak/2027-tech-jobs
    - dreamworkhq/Tech-Internships-2027
    - ApplyGuy/2027-Internships
    - SimplifyJobs/Summer2027-Internships
    - vanshb03/Summer2027-Internships
    - speedyapply/2027-SWE-College-Jobs (README.md and INTERN_INTL.md)
    - speedyapply/2027-AI-College-Jobs (README.md and INTERN_INTL.md)
    
    Banned:
    - pittcsc/Summer2027-Internships
    - SimplifyJobs/New-Grad-Positions (disabled but OK if commented out)
    """
    for source in SOURCES:
        # Ensure no banned sources
        assert "pittcsc" not in source.url.lower(), f"Banned source found: {source.url}"
        
        # Ensure internship-focused (has year 2027 or "intern" or "college" in URL)
        is_internship_focused = any(
            keyword in source.url.lower()
            for keyword in ["2027", "intern", "college", "summer"]
        )
        assert is_internship_focused, (
            f"Source does not appear internship-focused: {source.url}"
        )


def test_speedyapply_intl_source_present():
    """
    Verify speedyapply INTERN_INTL.md sources are present.
    
    PROJECT_SPEC planned these sources — they must be in the catalog.
    """
    intl_sources = [
        s for s in SOURCES 
        if "speedyapply" in s.url.lower() and "INTERN_INTL.md" in s.url
    ]
    
    assert len(intl_sources) == 2, (
        f"Expected exactly 2 speedyapply INTERN_INTL sources (SWE and AI), found {len(intl_sources)}: {[s.url for s in intl_sources]}"
    )
    
    for intl_source in intl_sources:
        assert intl_source.kind == "markdown", (
            f"speedyapply INTERN_INTL source should use markdown parser, got: {intl_source.kind}"
        )


def test_newgrad_sources_disabled():
    """
    Verify new-grad sources are still disabled (Rohan is internships-only).
    
    NEW_GRAD_INTL.md and NEW_GRAD_USA.md should NOT be in SOURCES.
    """
    newgrad_sources = [
        s for s in SOURCES 
        if "NEW_GRAD" in s.url or "new-grad" in s.name.lower()
    ]
    
    assert len(newgrad_sources) == 0, (
        f"New-grad sources should be disabled but found: {[s.url for s in newgrad_sources]}"
    )


def test_speedyapply_ai_sources_enabled():
    """
    Verify speedyapply AI College Jobs internship sources are enabled.
    
    Overnight #24: Add AI sibling repo internship sources (README.md and INTERN_INTL.md).
    """
    ai_sources = [s for s in SOURCES if "2027-AI-College-Jobs" in s.url]
    
    assert len(ai_sources) == 2, (
        f"Expected 2 AI College Jobs internship sources, found {len(ai_sources)}"
    )
    
    # Check for README.md (US internships)
    ai_readme = [s for s in ai_sources if s.url.endswith("README.md")]
    assert len(ai_readme) == 1, "Expected speedyapply-ai-2027 (README.md) to be enabled"
    assert ai_readme[0].name == "speedyapply-ai-2027"
    assert ai_readme[0].kind == "markdown"
    
    # Check for INTERN_INTL.md
    ai_intl = [s for s in ai_sources if "INTERN_INTL.md" in s.url]
    assert len(ai_intl) == 1, "Expected speedyapply-ai-intl-2027 (INTERN_INTL.md) to be enabled"
    assert ai_intl[0].name == "speedyapply-ai-intl-2027"
    assert ai_intl[0].kind == "markdown"


def test_speedyapply_ai_newgrad_banned():
    """
    Verify speedyapply AI College Jobs new-grad sources are NOT enabled.
    
    Policy: Rohan targets internships only. NEW_GRAD_USA.md and NEW_GRAD_INTL.md
    must NOT be in SOURCES.
    """
    ai_newgrad = [
        s for s in SOURCES
        if "2027-AI-College-Jobs" in s.url and "NEW_GRAD" in s.url
    ]
    
    assert len(ai_newgrad) == 0, (
        f"POLICY VIOLATION: AI new-grad sources are banned but found: {[s.url for s in ai_newgrad]}"
    )
