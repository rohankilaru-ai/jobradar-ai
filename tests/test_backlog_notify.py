"""Tests for Notion Backlog silent upsert and notification fine-tuning."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import (
    Notifier,
    is_link_probe_enabled,
    is_url_quality_good,
    is_within_notify_window,
    probe_url,
    should_send_alerts,
)


def test_url_quality_empty():
    """Empty URL should fail quality check."""
    assert is_url_quality_good("") is False
    assert is_url_quality_good("   ") is False


def test_url_quality_example_domains():
    """example.com and other bad patterns should fail quality check."""
    assert is_url_quality_good("https://example.com/job") is False
    assert is_url_quality_good("http://example.org/posting") is False
    assert is_url_quality_good("https://test.com/job") is False
    assert is_url_quality_good("http://localhost:3000/job") is False
    assert is_url_quality_good("http://127.0.0.1:8080/job") is False


def test_url_quality_good():
    """Real domains should pass quality check."""
    assert is_url_quality_good("https://stripe.com/jobs/123") is True
    assert is_url_quality_good("https://openai.com/careers/swe-intern") is True
    assert is_url_quality_good("https://jobs.lever.co/company/role") is True


def test_url_quality_invalid_scheme():
    """Invalid URLs should fail quality check."""
    assert is_url_quality_good("not-a-url") is False
    assert is_url_quality_good("ftp://example.com") is False  # example.com pattern blocks it
    assert is_url_quality_good("ftp://realsite.com/job") is True  # has valid scheme/netloc


def test_link_probe_disabled(monkeypatch):
    """When JOBRADAR_LINK_PROBE=0, probe should return True immediately."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    assert is_link_probe_enabled() is False
    assert probe_url("https://example.com/job") is True


def test_link_probe_enabled_default(monkeypatch):
    """Link probe should be enabled when JOBRADAR_LINK_PROBE is not 0."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    assert is_link_probe_enabled() is True


@patch("jobradar.notify.httpx.head")
def test_probe_url_success(mock_head, monkeypatch):
    """Successful probe should return True."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_head.return_value = mock_resp
    
    assert probe_url("https://stripe.com/jobs/123") is True
    mock_head.assert_called_once()


@patch("jobradar.notify.httpx.head")
def test_probe_url_404(mock_head, monkeypatch):
    """404 response should fail probe."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_head.return_value = mock_resp
    
    assert probe_url("https://stripe.com/jobs/404") is False


@patch("jobradar.notify.httpx.head")
def test_probe_url_exception(mock_head, monkeypatch):
    """Network error should fail probe gracefully."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    mock_head.side_effect = Exception("Connection failed")
    
    assert probe_url("https://unreachable.com/job") is False


def test_notify_window_recent_job():
    """Job first seen within 14 days should be within window."""
    now = datetime.now(timezone.utc)
    recent = now - timedelta(days=7)
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=recent.isoformat(),
    )
    assert is_within_notify_window(job) is True


def test_notify_window_old_job():
    """Job first seen more than 14 days ago should be outside window."""
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=20)
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=old.isoformat(),
    )
    assert is_within_notify_window(job) is False


def test_notify_window_edge():
    """Job exactly at 14-day boundary should be within window."""
    now = datetime.now(timezone.utc)
    edge = now - timedelta(days=14, hours=-1)  # 13 days, 23 hours
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=edge.isoformat(),
    )
    assert is_within_notify_window(job) is True


@patch("jobradar.notify.probe_url")
def test_should_send_alerts_good_job(mock_probe):
    """Job within window with good URL should pass."""
    mock_probe.return_value = True
    now = datetime.now(timezone.utc)
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=now.isoformat(),
    )
    assert should_send_alerts(job) is True


@patch("jobradar.notify.probe_url")
def test_should_send_alerts_outside_window(mock_probe):
    """Job outside window should not send alerts."""
    mock_probe.return_value = True
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=20)
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=old.isoformat(),
    )
    assert should_send_alerts(job) is False


def test_should_send_alerts_bad_url():
    """Job with bad URL should not send alerts."""
    now = datetime.now(timezone.utc)
    job = JobRecord(
        company="Test",
        title="SWE Intern",
        location="SF",
        url="https://example.com/job",
        first_seen_at=now.isoformat(),
    )
    assert should_send_alerts(job) is False


def test_should_send_alerts_empty_url():
    """Job with empty URL should not send alerts."""
    now = datetime.now(timezone.utc)
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="",
        first_seen_at=now.isoformat(),
    )
    assert should_send_alerts(job) is False


@patch("jobradar.notify.probe_url")
def test_should_send_alerts_failed_probe(mock_probe):
    """Job that fails probe should not send alerts."""
    mock_probe.return_value = False
    now = datetime.now(timezone.utc)
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/404",
        first_seen_at=now.isoformat(),
    )
    assert should_send_alerts(job) is False


def test_notifier_silent_mode(tmp_path):
    """Silent notification should only write JSONL, no Discord/ntfy/Telegram."""
    db = Database(tmp_path / "n.db")
    path = tmp_path / "notifications.jsonl"
    n = Notifier(path=path, db=db)
    
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        priority=True,
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram:
        
        result = n.notify(job, silent=True)
        assert result is True
        
        mock_discord.assert_not_called()
        mock_ntfy.assert_not_called()
        mock_telegram.assert_not_called()
    
    assert path.exists()
    content = path.read_text()
    assert "Stripe" in content
    assert '"silent": true' in content


def test_notifier_normal_mode(tmp_path):
    """Normal notification should write JSONL and attempt Discord/ntfy/Telegram."""
    db = Database(tmp_path / "n.db")
    path = tmp_path / "notifications.jsonl"
    n = Notifier(path=path, db=db)
    
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        priority=True,
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram:
        
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        
        result = n.notify(job, silent=False)
        assert result is True
        
        mock_discord.assert_called_once()
        mock_ntfy.assert_called_once()
        mock_telegram.assert_called_once()
    
    assert path.exists()
    content = path.read_text()
    assert "Stripe" in content
    assert '"silent": false' in content


def test_notifier_graceful_channel_failures(tmp_path):
    """Failed Discord/ntfy/Telegram should not abort notification."""
    db = Database(tmp_path / "n.db")
    path = tmp_path / "notifications.jsonl"
    n = Notifier(path=path, db=db)
    
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram:
        
        mock_discord.side_effect = Exception("Discord webhook failed")
        mock_ntfy.side_effect = Exception("ntfy failed")
        mock_telegram.side_effect = Exception("Telegram failed")
        
        result = n.notify(job, silent=False)
        assert result is True
    
    assert path.exists()


def test_notifier_respects_db_dedupe(tmp_path):
    """Second notification of same job should be skipped."""
    db = Database(tmp_path / "n.db")
    path = tmp_path / "notifications.jsonl"
    n = Notifier(path=path, db=db)
    
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord:
        mock_discord.return_value = "ok"
        
        assert n.notify(job, silent=False) is True
        assert n.notify(job, silent=False) is False
        
        mock_discord.assert_called_once()


def test_pipeline_backlog_old_job(tmp_path, monkeypatch):
    """Pipeline should upsert old job as Backlog without Discord/ntfy alerts."""
    from jobradar.pipeline import run_scan
    
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    db = Database(tmp_path / "p.db")
    
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=20)
    
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=old.isoformat(),
        last_seen_at=old.isoformat(),
    )
    
    stored, is_new = db.upsert_job(job)
    assert is_new is True
    
    with patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notion.configured") as mock_notion_configured, \
         patch("jobradar.notion.upsert_job") as mock_notion_upsert:
        
        mock_notion_configured.return_value = False
        
        stats = run_scan(db=db, sources=[])
        
        assert stats.notified == 0
        mock_discord.assert_not_called()


def test_pipeline_alert_recent_good_job(tmp_path, monkeypatch):
    """Recent job with good URL should trigger Discord/ntfy alerts."""
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")  # Disable probe for test speed
    db = Database(tmp_path / "p.db")
    notifier = Notifier(path=tmp_path / "n.jsonl", db=db)
    
    now = datetime.now(timezone.utc)
    
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/jobs/123",
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram:
        
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        
        from jobradar.notify import should_send_alerts
        assert should_send_alerts(job) is True
        
        result = notifier.notify(job, silent=False)
        assert result is True
        
        mock_discord.assert_called_once()
        mock_ntfy.assert_called_once()
        mock_telegram.assert_called_once()


def test_pipeline_backlog_bad_url(tmp_path, monkeypatch):
    """Pipeline should not alert job with bad URL (example.com)."""
    from jobradar.pipeline import run_scan
    
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    db = Database(tmp_path / "p.db")
    
    now = datetime.now(timezone.utc)
    
    job = JobRecord(
        company="Test",
        title="SWE Intern",
        location="SF",
        url="https://example.com/job",
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
    )
    
    stored, is_new = db.upsert_job(job)
    assert is_new is True
    
    with patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notion.configured") as mock_notion_configured:
        
        mock_notion_configured.return_value = False
        
        stats = run_scan(db=db, sources=[])
        
        mock_discord.assert_not_called()


def test_pipeline_no_notion_for_non_alert_jobs(tmp_path, monkeypatch):
    """Non-alert jobs should NOT create Notion pages (fix for Backlog flooding)."""
    from jobradar.pipeline import run_scan
    from jobradar.scout import ScoutResult
    from jobradar import pipeline as pipeline_mod
    
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")  # Speed up test
    db = Database(tmp_path / "p.db")
    
    # Pre-seed so we're not in seed_mode
    db.upsert_job(JobRecord(company="Seed", title="Init", location="SF", url="https://seed.com/1", sources=["seed"]))
    
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=20)
    
    # Create two jobs: one old (no alert), one new (alert)
    old_job = JobRecord(
        company="OldCo",
        title="Past Intern",
        location="Remote",
        url="https://oldco.com/jobs/123",
        sources=["test"],
        first_seen_at=old.isoformat(),
        last_seen_at=old.isoformat(),
    )
    
    new_job = JobRecord(
        company="NewCo",
        title="Fresh Intern",
        location="SF",
        url="https://newco.com/jobs/456",
        sources=["test"],
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
    )
    
    def fake_scout(db_arg, sources=None):
        return [ScoutResult(source="test", jobs=[old_job, new_job], not_modified=False, error=None)]
    
    monkeypatch.setattr(pipeline_mod, "scout_all", fake_scout)
    
    with patch("jobradar.notify.send_discord") as mock_discord, \
         patch("jobradar.notify.send_ntfy") as mock_ntfy, \
         patch("jobradar.notify.send_telegram") as mock_telegram, \
         patch("jobradar.notion.configured") as mock_notion_configured, \
         patch("jobradar.notion.upsert_job") as mock_notion_upsert:
        
        mock_discord.return_value = "ok"
        mock_ntfy.return_value = "ok"
        mock_telegram.return_value = "ok"
        mock_notion_configured.return_value = True
        
        stats = run_scan(db=db, sources=[])
        
        # Verify stats: 2 fetched, 2 kept, 2 new, 1 notified (only the recent job)
        assert stats.fetched == 2
        assert stats.kept == 2
        assert stats.new == 2
        assert stats.notified == 1
        
        # Discord/ntfy/telegram should be called once (for new_job only)
        assert mock_discord.call_count == 1
        assert mock_ntfy.call_count == 1
        assert mock_telegram.call_count == 1
        
        # Notion should ONLY be called once (for the alert-worthy new_job)
        # NOT for the old_job which is outside the notify window
        assert mock_notion_upsert.call_count == 1
        
        # Verify the Notion call was for the new job with STATUS_SEEN
        call_args = mock_notion_upsert.call_args
        assert call_args[0][0].company == "NewCo"
        assert call_args[1]["status"] == "Seen"
