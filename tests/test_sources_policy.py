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
    - speedyapply/2027-SWE-College-Jobs
    
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
