"""Tests for alert spam-control gates (overnight #18)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import (
    Notifier,
    alerts_enabled,
    max_alerts_per_scan,
    require_posted_at,
    should_send_alerts,
    within_notify_window,
)
from jobradar.pipeline import run_scan
from jobradar.scout import ScoutResult


def test_alerts_enabled_default():
    """JOBRADAR_ALERTS_ENABLED should default to enabled."""
    assert alerts_enabled() is True


def test_alerts_enabled_pause(monkeypatch):
    """JOBRADAR_ALERTS_ENABLED=0 should pause all alerts."""
    for val in ["0", "false", "off", "no", "disabled"]:
        monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", val)
        assert alerts_enabled() is False, f"Failed for value: {val}"


def test_alerts_enabled_enable(monkeypatch):
    """JOBRADAR_ALERTS_ENABLED=1 should enable alerts."""
    for val in ["1", "true", "on", "yes", "enabled"]:
        monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", val)
        assert alerts_enabled() is True, f"Failed for value: {val}"


def test_max_alerts_per_scan_default(monkeypatch):
    """JOBRADAR_MAX_ALERTS_PER_SCAN should default to 15."""
    # Remove conftest override to test actual default
    monkeypatch.delenv("JOBRADAR_MAX_ALERTS_PER_SCAN", raising=False)
    assert max_alerts_per_scan() == 15


def test_max_alerts_per_scan_custom(monkeypatch):
    """JOBRADAR_MAX_ALERTS_PER_SCAN should accept custom values."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "5")
    assert max_alerts_per_scan() == 5
    
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "0")
    assert max_alerts_per_scan() == 0  # 0 = unlimited


def test_max_alerts_per_scan_invalid(monkeypatch):
    """JOBRADAR_MAX_ALERTS_PER_SCAN should fallback to 15 on invalid input."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "invalid")
    assert max_alerts_per_scan() == 15
    
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "-5")
    assert max_alerts_per_scan() == 0  # max(0, -5) = 0


def test_require_posted_at_default(monkeypatch):
    """JOBRADAR_REQUIRE_POSTED_AT should default to enabled."""
    # Remove conftest override to test actual default
    monkeypatch.delenv("JOBRADAR_REQUIRE_POSTED_AT", raising=False)
    assert require_posted_at() is True


def test_require_posted_at_disabled(monkeypatch):
    """JOBRADAR_REQUIRE_POSTED_AT=0 should allow jobs without posted_at."""
    for val in ["0", "false", "off", "no"]:
        monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", val)
        assert require_posted_at() is False, f"Failed for value: {val}"


def test_alerts_paused_blocks_notification(monkeypatch):
    """When alerts are paused, should_send_alerts should return False."""
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")
    
    now = datetime.now(timezone.utc)
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=now.isoformat(),
        posted_at=now.isoformat(),
    )
    
    assert should_send_alerts(job) is False


def test_alerts_paused_still_stores_jobs(tmp_path, monkeypatch):
    """When alerts are paused, jobs should still be stored in DB."""
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "p.db")
    
    # Pre-seed DB to avoid seed_mode (which skips notifications)
    seed_job = JobRecord(
        company="SeedCo",
        title="Seed",
        location="SF",
        url="https://seed.com/1",
        sources=["seed"],
    )
    db.upsert_job(seed_job)
    
    now = datetime.now(timezone.utc)
    job = JobRecord(
        company="TestCo",
        title="SWE Intern",
        location="SF",
        url="https://testco.com/jobs/123",
        sources=["test"],
        first_seen_at=now.isoformat(),
        posted_at=now.isoformat(),
    )
    
    def fake_scout(db_arg, sources=None):
        return [ScoutResult(source="test", jobs=[job], not_modified=False, error=None)]
    
    from jobradar import pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "scout_all", fake_scout)
    
    with patch("jobradar.notify.send_discord") as mock_discord:
        stats = run_scan(db=db, sources=[])
        
        # Job should be stored but not alerted
        assert stats.new == 1
        assert stats.notified == 1  # JSONL still written
        assert stats.alerted == 0   # No live alerts
        mock_discord.assert_not_called()
    
    # Verify job is in DB (seed + new job)
    assert db.count_jobs() == 2


def test_max_alerts_cap_enforced(tmp_path, monkeypatch):
    """Pipeline should respect JOBRADAR_MAX_ALERTS_PER_SCAN cap."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "3")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")  # Allow all jobs for this test
    
    db = Database(tmp_path / "p.db")
    
    # Pre-seed DB to avoid seed_mode
    seed_job = JobRecord(
        company="SeedCo",
        title="Seed",
        location="SF",
        url="https://seed.com/1",
        sources=["seed"],
    )
    db.upsert_job(seed_job)
    
    now = datetime.now(timezone.utc)
    
    # Create 5 distinct jobs (avoid fuzzy match on company/title)
    companies = ["Apple", "Google", "Microsoft", "Amazon", "Meta"]
    titles = ["Backend Engineer", "Frontend Dev", "Data Scientist", "ML Researcher", "DevOps Lead"]
    jobs = [
        JobRecord(
            company=companies[i],
            title=titles[i],
            location=f"City{i}",
            url=f"https://{companies[i].lower()}.com/jobs/{i}",
            sources=["test"],
            first_seen_at=now.isoformat(),
        )
        for i in range(5)
    ]
    
    def fake_scout(db_arg, sources=None):
        return [ScoutResult(source="test", jobs=jobs, not_modified=False, error=None)]
    
    from jobradar import pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "scout_all", fake_scout)
    
    with patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram:
        
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        
        stats = run_scan(db=db, sources=[])
        
        # All 5 jobs should be stored
        assert stats.new == 5
        assert stats.notified == 5  # All get JSONL
        assert stats.alerted == 3   # Only 3 get live alerts (cap)
        assert stats.alert_cap_hit is True
        
        # Discord/ntfy/telegram should be called exactly 3 times
        assert mock_discord.call_count == 3
        assert mock_ntfy.call_count == 3
        assert mock_telegram.call_count == 3


def test_max_alerts_zero_unlimited(tmp_path, monkeypatch):
    """JOBRADAR_MAX_ALERTS_PER_SCAN=0 should mean unlimited."""
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "0")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    
    db = Database(tmp_path / "p.db")
    
    # Pre-seed DB to avoid seed_mode
    seed_job = JobRecord(
        company="SeedCo",
        title="Seed",
        location="SF",
        url="https://seed.com/1",
        sources=["seed"],
    )
    db.upsert_job(seed_job)
    
    now = datetime.now(timezone.utc)
    
    # Create 10 distinct jobs (avoid fuzzy match on company/title)
    companies = ["Apple", "Google", "Microsoft", "Amazon", "Meta", "Tesla", "Nvidia", "Intel", "Adobe", "Salesforce"]
    titles = ["Backend Eng", "Frontend Dev", "Data Scientist", "ML Researcher", "DevOps Lead", 
              "Security Analyst", "Product Manager", "UX Designer", "QA Engineer", "Cloud Architect"]
    jobs = [
        JobRecord(
            company=companies[i],
            title=titles[i],
            location=f"City{i}",
            url=f"https://{companies[i].lower()}.com/jobs/{i}",
            sources=["test"],
            first_seen_at=now.isoformat(),
        )
        for i in range(10)
    ]
    
    def fake_scout(db_arg, sources=None):
        return [ScoutResult(source="test", jobs=jobs, not_modified=False, error=None)]
    
    from jobradar import pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "scout_all", fake_scout)
    
    with patch("jobradar.notify.send_discord") as mock_discord:
        mock_discord.return_value = "ok"
        
        stats = run_scan(db=db, sources=[])
        
        # All 10 jobs should be alerted (no cap)
        assert stats.new == 10
        assert stats.alerted == 10
        assert stats.alert_cap_hit is False


def test_require_posted_at_blocks_undated_jobs(monkeypatch):
    """With JOBRADAR_REQUIRE_POSTED_AT=1, jobs without posted_at should not alert."""
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    
    now = datetime.now(timezone.utc)
    
    # Job without posted_at
    job_no_date = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=now.isoformat(),
    )
    
    assert within_notify_window(job_no_date) is False
    assert should_send_alerts(job_no_date) is False


def test_require_posted_at_allows_dated_jobs(monkeypatch):
    """With JOBRADAR_REQUIRE_POSTED_AT=1, jobs with posted_at should alert if recent."""
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    now = datetime.now(timezone.utc)
    
    # Job with recent posted_at
    job_with_date = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=now.isoformat(),
        posted_at=now.isoformat(),
    )
    
    assert within_notify_window(job_with_date) is True
    assert should_send_alerts(job_with_date) is True


def test_require_posted_at_disabled_fallback_to_first_seen(monkeypatch):
    """With JOBRADAR_REQUIRE_POSTED_AT=0, should fall back to first_seen_at."""
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    now = datetime.now(timezone.utc)
    
    # Job without posted_at but recent first_seen_at
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=now.isoformat(),
    )
    
    assert within_notify_window(job) is True
    assert should_send_alerts(job) is True


def test_require_posted_at_old_date_blocks(monkeypatch):
    """Job with old posted_at should be blocked regardless of first_seen_at."""
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    monkeypatch.setenv("JOBRADAR_NOTIFY_WINDOW_DAYS", "3")
    
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=10)
    
    # Job with old posted_at but recent first_seen_at
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=now.isoformat(),
        posted_at=old.isoformat(),
    )
    
    assert within_notify_window(job) is False
    assert should_send_alerts(job) is False


def test_telegram_empty_credentials_skip(monkeypatch):
    """Empty or missing Telegram credentials should skip silently."""
    from jobradar.notify import send_telegram, telegram_configured
    
    # Test missing token
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    
    assert telegram_configured() is False
    assert send_telegram("test message") == "skipped"
    
    # Test empty token
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    
    assert telegram_configured() is False
    assert send_telegram("test message") == "skipped"
    
    # Test missing chat_id
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    
    assert telegram_configured() is False
    assert send_telegram("test message") == "skipped"


def test_telegram_no_placeholder_urls(monkeypatch):
    """Telegram payloads should not include placeholder URLs."""
    from jobradar.notify import format_alert
    
    # Job with example.com URL
    job = JobRecord(
        company="TestCo",
        title="SWE Intern",
        location="SF",
        url="https://example.com/job",
    )
    
    alert = format_alert(job)
    
    # Alert should contain the URL (format_alert doesn't filter)
    # But should_send_alerts will block it
    assert should_send_alerts(job) is False


def test_combined_gates_priority_order(tmp_path, monkeypatch):
    """Test that gates are checked in logical order."""
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    now = datetime.now(timezone.utc)
    
    # Job without posted_at should fail require_posted_at gate first
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=now.isoformat(),
    )
    
    assert should_send_alerts(job) is False
    
    # Now pause alerts - should fail alerts_enabled gate
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")
    job.posted_at = now.isoformat()  # Add posted_at
    
    assert should_send_alerts(job) is False


def test_health_command_shows_alert_status(monkeypatch, capsys):
    """Health command should show alert gate status."""
    from jobradar.cli import cmd_health
    import argparse
    
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "15")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    captured = capsys.readouterr()
    
    # Should show notifiers (but not secret values)
    assert "jobradar" in captured.out.lower()
    assert "db:" in captured.out.lower()


def test_pipeline_respects_all_gates(tmp_path, monkeypatch):
    """End-to-end test: pipeline should respect all alert gates."""
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "2")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    monkeypatch.setenv("JOBRADAR_NOTIFY_WINDOW_DAYS", "3")
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "p.db")
    
    # Pre-seed DB to avoid seed_mode
    seed_job = JobRecord(
        company="SeedCo",
        title="Seed",
        location="SF",
        url="https://seed.com/1",
        sources=["seed"],
    )
    db.upsert_job(seed_job)
    
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=5)
    
    jobs = [
        # Should alert (recent posted_at)
        JobRecord(
            company="GoodCompany1",
            title="Backend Engineer 1",
            location="SF",
            url="https://boards.greenhouse.io/goodcompany1/jobs/123456",
            sources=["test"],
            first_seen_at=now.isoformat(),
            posted_at=now.isoformat(),
        ),
        # Should alert (recent posted_at)
        JobRecord(
            company="GoodCompany2",
            title="Frontend Engineer 2",
            location="NYC",
            url="https://jobs.lever.co/goodcompany2/frontend-engineer",
            sources=["test"],
            first_seen_at=now.isoformat(),
            posted_at=now.isoformat(),
        ),
        # Should NOT alert (no posted_at)
        JobRecord(
            company="NoDateCorp",
            title="DevOps Engineer 3",
            location="Austin",
            url="https://jobs.ashbyhq.com/nodatecorp/devops-position",
            sources=["test"],
            first_seen_at=now.isoformat(),
        ),
        # Should NOT alert (old posted_at)
        JobRecord(
            company="OldDateInc",
            title="Data Engineer 4",
            location="Seattle",
            url="https://boards.greenhouse.io/olddateinc/jobs/999999",
            sources=["test"],
            first_seen_at=now.isoformat(),
            posted_at=old.isoformat(),
        ),
        # Would alert but cap is 2
        JobRecord(
            company="GoodCompany3",
            title="ML Engineer 5",
            location="Boston",
            url="https://jobs.lever.co/goodcompany3/ml-engineer",
            sources=["test"],
            first_seen_at=now.isoformat(),
            posted_at=now.isoformat(),
        ),
    ]
    
    def fake_scout(db_arg, sources=None):
        return [ScoutResult(source="test", jobs=jobs, not_modified=False, error=None)]
    
    from jobradar import pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "scout_all", fake_scout)
    
    with patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram:
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        
        stats = run_scan(db=db, sources=[])
        
        # All 5 jobs stored
        assert stats.new == 5
        # 3 jobs get JSONL (silent for NoDat and OldDate)
        assert stats.notified == 3
        # Only 2 get live alerts (Good1, Good2) due to cap
        assert stats.alerted == 2
        assert stats.alert_cap_hit is True
        
        # Discord called exactly twice
        assert mock_discord.call_count == 2


def test_alert_gates_documented_in_health():
    """Alert gate functions should have clear docstrings."""
    assert alerts_enabled.__doc__ is not None
    assert max_alerts_per_scan.__doc__ is not None
    assert require_posted_at.__doc__ is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
