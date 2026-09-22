"""Lock the canonical notify window default at 14 days (PR #45, overnight #27).

This test catches code/docs drift by verifying:
1. The NOTIFY_WINDOW_DAYS constant is 14 (not 3)
2. The default behavior uses 14 days when no env override is set
3. Environment variable overrides still work correctly

Context: Overnight #35 audited and normalized notify window documentation drift.
The agreed canonical default is 14 days, shipped in PR #45 (overnight #27).
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from jobradar.models import JobRecord
from jobradar.notify import NOTIFY_WINDOW_DAYS, within_notify_window


def test_notify_window_constant_is_14_days():
    """Lock: NOTIFY_WINDOW_DAYS constant must be 14 (not 3)."""
    assert NOTIFY_WINDOW_DAYS == 14, (
        "NOTIFY_WINDOW_DAYS constant should be 14 days per PR #45. "
        "If you changed this, update docs (README, PROJECT_SPEC, HANDOFF, "
        "LIVE_SCAN_VALIDATION, CLOUD_SCAN, .env.example, cloud-scan.yml)."
    )


def test_default_behavior_uses_14_days(monkeypatch):
    """Lock: Default notify window behavior is 14 days (no env override)."""
    # Clear any existing override
    monkeypatch.delenv("JOBRADAR_NOTIFY_WINDOW_DAYS", raising=False)
    
    now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    
    # 13 days ago: inside 14-day window
    posted_13d = (now - timedelta(days=13)).date().isoformat()
    job_inside = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://example.com/1",
        posted_at=posted_13d,
    )
    assert within_notify_window(job_inside, now=now) is True, (
        "Job posted 13 days ago should be inside default 14-day window"
    )
    
    # 15 days ago: outside 14-day window
    posted_15d = (now - timedelta(days=15)).date().isoformat()
    job_outside = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://example.com/2",
        posted_at=posted_15d,
    )
    assert within_notify_window(job_outside, now=now) is False, (
        "Job posted 15 days ago should be outside default 14-day window"
    )


def test_env_override_still_works(monkeypatch):
    """Verify JOBRADAR_NOTIFY_WINDOW_DAYS env override still works."""
    monkeypatch.setenv("JOBRADAR_NOTIFY_WINDOW_DAYS", "7")
    
    now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    
    # 6 days ago: inside 7-day override window
    posted_6d = (now - timedelta(days=6)).date().isoformat()
    job_inside = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://example.com/1",
        posted_at=posted_6d,
    )
    assert within_notify_window(job_inside, now=now) is True
    
    # 8 days ago: outside 7-day override window
    posted_8d = (now - timedelta(days=8)).date().isoformat()
    job_outside = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://example.com/2",
        posted_at=posted_8d,
    )
    assert within_notify_window(job_outside, now=now) is False


def test_boundary_case_exactly_14_days(monkeypatch):
    """Test boundary: job posted exactly 14 days ago should be outside window."""
    monkeypatch.delenv("JOBRADAR_NOTIFY_WINDOW_DAYS", raising=False)
    
    now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    posted_14d = (now - timedelta(days=14)).date().isoformat()
    
    job = JobRecord(
        company="Acme",
        title="SWE Intern",
        url="https://example.com/1",
        posted_at=posted_14d,
    )
    
    # Exactly 14 days ago should be outside the window (strict < comparison)
    assert within_notify_window(job, now=now) is False, (
        "Job posted exactly 14 days ago should be outside window (strict <)"
    )
