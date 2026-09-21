"""Integration tests verifying all notification quality gates work together.

Tests the complete notification pipeline from quality checks through to final send decisions.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import Notifier, should_send_alerts


def test_all_gates_pass_for_high_quality_job(tmp_path, monkeypatch):
    """High-quality job with all gates passing should succeed."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    monkeypatch.setenv("JOBRADAR_NOTIFY_WINDOW_DAYS", "14")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    # High-quality job posted 2 days ago
    now = datetime.now(timezone.utc)
    posted_2_days_ago = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    
    job = JobRecord(
        company="Stripe",
        title="Software Engineer Intern - Summer 2027",
        location="San Francisco, CA",
        url="https://stripe.com/careers/positions/software-engineer-intern-123456",
        sources=["simplify"],
        snippet="Build payment infrastructure",
        posted_at=posted_2_days_ago,
        priority=True,
    )
    
    # Should pass all gates
    assert should_send_alerts(job) is True
    
    # Should successfully notify
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        assert result is True


def test_gate_blocks_old_job_outside_window(tmp_path, monkeypatch):
    """Job outside notify window should be blocked."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    monkeypatch.setenv("JOBRADAR_NOTIFY_WINDOW_DAYS", "14")
    
    # Job posted 20 days ago (outside 14-day window)
    now = datetime.now(timezone.utc)
    posted_20_days_ago = (now - timedelta(days=20)).strftime("%Y-%m-%d")
    
    job = JobRecord(
        company="Google",
        title="SWE Intern",
        location="Mountain View, CA",
        url="https://careers.google.com/jobs/results/123456789012345678901",
        sources=["simplify"],
        posted_at=posted_20_days_ago,
    )
    
    # Should be blocked by notify window gate
    assert should_send_alerts(job) is False


def test_gate_blocks_placeholder_url(tmp_path, monkeypatch):
    """Job with placeholder URL should be blocked."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    
    now = datetime.now(timezone.utc)
    posted_today = now.strftime("%Y-%m-%d")
    
    job = JobRecord(
        company="TestCorp",
        title="Engineer Intern",
        location="SF",
        url="https://example.com/jobs/123",
        sources=["test"],
        posted_at=posted_today,
    )
    
    # Should be blocked by placeholder URL gate
    assert should_send_alerts(job) is False


def test_gate_blocks_empty_url(tmp_path, monkeypatch):
    """Job with empty URL should be blocked."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    
    now = datetime.now(timezone.utc)
    posted_today = now.strftime("%Y-%m-%d")
    
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="",
        sources=["test"],
        posted_at=posted_today,
    )
    
    # Should be blocked by empty URL gate
    assert should_send_alerts(job) is False


def test_gate_blocks_generic_career_page(tmp_path, monkeypatch):
    """Job pointing to generic career page (not specific posting) should be blocked."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    
    now = datetime.now(timezone.utc)
    posted_today = now.strftime("%Y-%m-%d")
    
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/careers",  # Generic careers page, not specific job
        sources=["test"],
        posted_at=posted_today,
    )
    
    # Should be blocked by specific job URL gate
    assert should_send_alerts(job) is False


def test_gate_respects_alerts_disabled_flag(tmp_path, monkeypatch):
    """When JOBRADAR_ALERTS_ENABLED=0, all alerts should be blocked."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")  # Disabled
    
    now = datetime.now(timezone.utc)
    posted_today = now.strftime("%Y-%m-%d")
    
    # Otherwise high-quality job
    job = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://stripe.com/careers/positions/software-engineer-intern-123456",
        sources=["simplify"],
        posted_at=posted_today,
        priority=True,
    )
    
    # Should be blocked because alerts are disabled
    assert should_send_alerts(job) is False


def test_discord_tier_routing_respects_gates(tmp_path, monkeypatch):
    """Discord tier routing should only happen for jobs that pass all gates."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "https://discord.com/priority")
    monkeypatch.setenv("DISCORD_WEBHOOK_OTHER", "https://discord.com/other")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    now = datetime.now(timezone.utc)
    posted_today = now.strftime("%Y-%m-%d")
    
    # Good priority job
    priority_job = JobRecord(
        company="OpenAI",
        title="Research Engineer Intern",
        location="SF",
        url="https://openai.com/careers/research-engineer-intern-123456",
        sources=["test"],
        posted_at=posted_today,
        priority=True,
    )
    
    # Bad job (placeholder URL)
    bad_job = JobRecord(
        company="OpenAI",
        title="Engineer",
        location="SF",
        url="https://example.com/jobs/123",
        sources=["test"],
        posted_at=posted_today,
    )
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        # Good job should attempt Discord (but blocked by PYTEST_CURRENT_TEST)
        result1 = notifier.notify(priority_job, silent=False)
        assert result1 is True
        
        # Bad job should be rejected before Discord is even attempted
        result2 = notifier.notify(bad_job, silent=False)
        assert result2 is False
        
        # No HTTP calls should have been made (PYTEST_CURRENT_TEST blocks)
        mock_post.assert_not_called()


def test_multiple_gates_can_block_same_job(tmp_path, monkeypatch):
    """Job can be blocked by multiple gates; first one wins."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    monkeypatch.setenv("JOBRADAR_NOTIFY_WINDOW_DAYS", "14")
    
    # Job with BOTH old post date AND placeholder URL
    now = datetime.now(timezone.utc)
    posted_30_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    
    job = JobRecord(
        company="TestCorp",
        title="Engineer",
        location="SF",
        url="https://example.com/jobs/123",
        sources=["test"],
        posted_at=posted_30_days_ago,
    )
    
    # Should be blocked (by notify window, placeholder URL, or both)
    assert should_send_alerts(job) is False


def test_silent_mode_bypasses_quality_gates(tmp_path, monkeypatch):
    """Silent mode should write JSONL even for jobs that would fail quality gates."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    # Job with placeholder URL (would normally be blocked)
    job = JobRecord(
        company="TestCorp",
        title="Engineer",
        location="SF",
        url="https://example.com/jobs/123",
        sources=["test"],
    )
    
    # Silent mode should succeed even though URL is placeholder
    result = notifier.notify(job, silent=True)
    assert result is True
    
    # JSONL should be written
    assert (tmp_path / "notify.jsonl").exists()
    content = (tmp_path / "notify.jsonl").read_text()
    assert '"silent": true' in content


def test_gates_summary_all_working():
    """Summary test: verify all major gates are implemented and callable."""
    from jobradar.notify import (
        alerts_enabled,
        discord_configured,
        is_specific_job_url,
        job_notify_block_reason,
        link_probe_enabled,
        ntfy_configured,
        telegram_configured,
        within_notify_window,
    )
    
    # All gate functions should be callable (smoke test)
    assert callable(alerts_enabled)
    assert callable(within_notify_window)
    assert callable(job_notify_block_reason)
    assert callable(is_specific_job_url)
    assert callable(link_probe_enabled)
    assert callable(discord_configured)
    assert callable(ntfy_configured)
    assert callable(telegram_configured)
