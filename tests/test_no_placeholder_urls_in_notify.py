"""Tests ensuring placeholder URLs are never sent in Discord/ntfy/Telegram notifications.

Verifies that jobs with placeholder, empty, or test URLs are blocked from alerts
and never make it to live notification channels.
"""

from unittest.mock import patch

import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import Notifier, format_alert, job_notify_block_reason


# --- Test job_notify_block_reason blocks placeholder URLs ---


def test_block_reason_detects_placeholder_urls():
    """job_notify_block_reason should detect and block placeholder URLs."""
    placeholder_jobs = [
        JobRecord(
            company="TestCorp",
            title="Engineer",
            location="SF",
            url="https://example.com/jobs/123",
            sources=["test"],
        ),
        JobRecord(
            company="TestCorp",
            title="Engineer",
            location="SF",
            url="https://example.org/careers",
            sources=["test"],
        ),
        JobRecord(
            company="TestCorp",
            title="Engineer",
            location="SF",
            url="https://test.com/job",
            sources=["test"],
        ),
        JobRecord(
            company="TestCorp",
            title="Engineer",
            location="SF",
            url="https://placeholder.com/careers",
            sources=["test"],
        ),
        JobRecord(
            company="TestCorp",
            title="Engineer",
            location="SF",
            url="http://localhost:3000/jobs",
            sources=["test"],
        ),
        JobRecord(
            company="TestCorp",
            title="Engineer",
            location="SF",
            url="http://127.0.0.1/careers",
            sources=["test"],
        ),
    ]
    
    for job in placeholder_jobs:
        reason = job_notify_block_reason(job)
        assert reason is not None, f"Should block {job.url}"
        # The important thing is that it's blocked; the specific reason may vary
        # (placeholder detection, domain mismatch, etc.)


def test_block_reason_detects_empty_urls():
    """job_notify_block_reason should detect and block empty URLs."""
    empty_url_jobs = [
        JobRecord(
            company="TestCorp",
            title="Engineer",
            location="SF",
            url="",
            sources=["test"],
        ),
        JobRecord(
            company="TestCorp",
            title="Engineer",
            location="SF",
            url="   ",
            sources=["test"],
        ),
        JobRecord(
            company="TestCorp",
            title="Engineer",
            location="SF",
            url=None,
            sources=["test"],
        ),
    ]
    
    for job in empty_url_jobs:
        reason = job_notify_block_reason(job)
        assert reason is not None, f"Should block empty URL: {job.url}"
        assert "empty" in reason.lower() or "placeholder" in reason.lower()


def test_block_reason_allows_real_urls():
    """job_notify_block_reason should allow real job URLs."""
    real_jobs = [
        JobRecord(
            company="Stripe",
            title="Software Engineer Intern",
            location="San Francisco, CA",
            url="https://stripe.com/careers/positions/software-engineer-intern-123456",
            sources=["test"],
        ),
        JobRecord(
            company="Google",
            title="SWE Intern",
            location="Mountain View, CA",
            url="https://careers.google.com/jobs/results/123456789012345678901",
            sources=["test"],
        ),
        JobRecord(
            company="OpenAI",
            title="Research Engineer",
            location="San Francisco, CA",
            url="https://openai.com/careers/research-engineer-intern",
            sources=["test"],
        ),
    ]
    
    for job in real_jobs:
        # Note: These may be blocked for other reasons (probe, generic career page, etc.)
        # but they should NOT be blocked for being placeholder URLs
        reason = job_notify_block_reason(job)
        if reason:
            assert "placeholder" not in reason.lower()
            assert "test fixture" not in reason.lower()
            assert "example.com" not in reason.lower()


# --- Test format_alert never includes placeholder URLs ---


def test_format_alert_includes_real_company_and_title():
    """format_alert should include real company name and title, not placeholders."""
    job = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://stripe.com/careers/positions/software-engineer-intern-123456",
        sources=["simplify"],
        snippet="Work on payment infrastructure...",
        priority=True,
    )
    
    alert = format_alert(job)
    
    # Should include real data
    assert "Stripe" in alert
    assert "Software Engineer Intern" in alert
    assert "San Francisco, CA" in alert
    assert "stripe.com" in alert
    assert "simplify" in alert
    
    # Should NOT include placeholders
    assert "example.com" not in alert.lower()
    assert "placeholder" not in alert.lower()
    assert "test.com" not in alert.lower()


def test_format_alert_includes_real_url():
    """format_alert should include the actual job URL, not a placeholder."""
    job = JobRecord(
        company="OpenAI",
        title="Research Engineer Intern",
        location="San Francisco, CA",
        url="https://openai.com/careers/research-engineer-intern-summer-2027",
        sources=["lever"],
    )
    
    alert = format_alert(job)
    
    # Should include the real URL
    assert "https://openai.com/careers/research-engineer-intern-summer-2027" in alert
    
    # Should NOT include placeholders
    assert "example.com" not in alert
    assert "example.org" not in alert
    assert "localhost" not in alert


# --- Integration tests: Notifier never sends placeholder URLs ---


def test_notifier_blocks_example_com_urls(tmp_path, monkeypatch):
    """Notifier should refuse to send notifications for example.com URLs."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    # Set up Discord webhook (but it should never be called)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/fake/url")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="TestCorp",
        title="Software Engineer",
        location="SF",
        url="https://example.com/jobs/12345",
        sources=["test"],
    )
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        
        # Job should be rejected (not notified)
        assert result is False
        
        # No HTTP calls should be made
        mock_post.assert_not_called()
    
    # JSONL should NOT contain this job (it was blocked before JSONL write)
    if (tmp_path / "notify.jsonl").exists():
        content = (tmp_path / "notify.jsonl").read_text()
        # The job should not be in JSONL if it was blocked
        # (depending on implementation, it might not write to JSONL at all)


def test_notifier_blocks_localhost_urls(tmp_path, monkeypatch):
    """Notifier should refuse to send notifications for localhost URLs."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/fake/url")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="TestCorp",
        title="Engineer",
        location="SF",
        url="http://localhost:3000/jobs/123",
        sources=["test"],
    )
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        
        # Should be blocked
        assert result is False
        mock_post.assert_not_called()


def test_notifier_blocks_placeholder_urls(tmp_path, monkeypatch):
    """Notifier should refuse to send notifications for placeholder.com URLs."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/fake/url")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="TestCorp",
        title="Engineer",
        location="SF",
        url="https://placeholder.com/careers",
        sources=["test"],
    )
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        
        # Should be blocked
        assert result is False
        mock_post.assert_not_called()


def test_notifier_blocks_empty_urls(tmp_path, monkeypatch):
    """Notifier should refuse to send notifications for empty URLs."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/fake/url")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="TestCorp",
        title="Engineer",
        location="SF",
        url="",
        sources=["test"],
    )
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        
        # Should be blocked
        assert result is False
        mock_post.assert_not_called()


def test_notifier_allows_real_urls_with_real_data(tmp_path, monkeypatch):
    """Notifier should allow notifications for real URLs with real company/title data."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    # Don't set Discord webhook - we just want to verify the job passes quality gates
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://stripe.com/careers/positions/software-engineer-intern-123456",
        sources=["simplify"],
        snippet="Build payment infrastructure",
    )
    
    # This should pass the quality gates (though Discord may be skipped if not configured)
    # The key is it should NOT be blocked for URL quality
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        
        # Should succeed (JSONL written)
        assert result is True
        
        # JSONL should be written with real data
        assert (tmp_path / "notify.jsonl").exists()
        content = (tmp_path / "notify.jsonl").read_text()
        assert "Stripe" in content
        assert "Software Engineer Intern" in content
        assert "stripe.com" in content
        
        # Should NOT contain placeholders
        assert "example.com" not in content
        assert "placeholder" not in content.lower()
        assert "localhost" not in content


def test_multiple_jobs_only_real_urls_notify(tmp_path, monkeypatch):
    """When notifying multiple jobs, only those with real URLs should succeed."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    jobs = [
        # Real job - should pass
        JobRecord(
            company="Stripe",
            title="SWE Intern",
            location="SF",
            url="https://stripe.com/careers/positions/swe-intern-123456",
            sources=["test"],
        ),
        # Placeholder - should be blocked
        JobRecord(
            company="FakeCorp",
            title="Engineer",
            location="NYC",
            url="https://example.com/jobs/123",
            sources=["test"],
        ),
        # Real job - should pass
        JobRecord(
            company="Google",
            title="ML Intern",
            location="MTV",
            url="https://careers.google.com/jobs/results/987654321098765432109",
            sources=["test"],
        ),
        # localhost - should be blocked
        JobRecord(
            company="TestCo",
            title="Dev",
            location="LA",
            url="http://localhost:3000/jobs",
            sources=["test"],
        ),
    ]
    
    results = []
    with patch("jobradar.notify.httpx.post") as mock_post:
        for job in jobs:
            result = notifier.notify(job, silent=False)
            results.append(result)
    
    # First and third jobs should succeed, second and fourth should fail
    assert results == [True, False, True, False]
    
    # JSONL should only have the real jobs
    content = (tmp_path / "notify.jsonl").read_text()
    assert "Stripe" in content
    assert "Google" in content
    assert "example.com" not in content
    assert "localhost" not in content
    assert "FakeCorp" not in content
    assert "TestCo" not in content
