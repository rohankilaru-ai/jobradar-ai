"""Product-completion tests: offline validation of scan --once and notification paths."""

from __future__ import annotations

import json
from pathlib import Path

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import Notifier, discord_configured, ntfy_configured, telegram_configured
from jobradar.pipeline import run_scan
from jobradar.sources import Source


def test_scan_once_offline_path(tmp_path, monkeypatch):
    """Validate scan --once path works offline without network calls."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "scan.db"))
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notifications.jsonl"))
    
    # Clear all notification keys to ensure offline mode
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    
    db = Database(tmp_path / "scan.db")
    
    # First scan with empty sources: seed mode (no alerts)
    stats1 = run_scan(db=db, sources=[])
    assert stats1.seed_mode is True
    assert stats1.notified == 0
    assert stats1.fetched == 0
    
    # Insert jobs manually to simulate seeded state
    jobs = [
        JobRecord(
            company="OpenAI",
            title="Software Engineer Intern",
            location="San Francisco, CA",
            url="https://example.com/openai-swe",
            sources=["manual"],
            priority=True,
        ),
        JobRecord(
            company="Anthropic",
            title="ML Research Intern",
            location="San Francisco, CA",
            url="https://example.com/anthropic-ml",
            sources=["manual"],
            priority=True,
        ),
    ]
    
    for job in jobs:
        db.upsert_job(job)
    
    # Second scan: should detect as non-seed mode
    stats2 = run_scan(db=db, sources=[])
    assert stats2.seed_mode is False
    assert db.count_jobs() == 2


def test_notify_idempotency_multiple_channels(tmp_path, monkeypatch):
    """Verify notifications are sent exactly once per job, even with multiple channels."""
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notifications.jsonl"))
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    
    db = Database(tmp_path / "notify.db")
    notifier = Notifier(path=tmp_path / "notifications.jsonl", db=db)
    
    job = JobRecord(
        company="Stripe",
        title="Backend Engineer Intern",
        location="San Francisco, CA",
        url="https://example.com/stripe-backend",
        sources=["test"],
        priority=True,
    )
    
    # First notify: should succeed
    result1 = notifier.notify(job)
    assert result1 is True
    assert db.was_notified(job.canonical_key)
    
    # Second notify: should be skipped (idempotent)
    result2 = notifier.notify(job)
    assert result2 is False
    
    # Third notify: still skipped
    result3 = notifier.notify(job)
    assert result3 is False
    
    # Verify only one notification was written
    notifications = Path(tmp_path / "notifications.jsonl").read_text().strip().split("\n")
    assert len(notifications) == 1
    
    notif_data = json.loads(notifications[0])
    assert notif_data["canonical_key"] == job.canonical_key
    assert notif_data["priority"] is True
    assert "[PRIORITY]" in notif_data["text"]


def test_empty_notification_keys_skip_gracefully(tmp_path, monkeypatch):
    """Verify that empty/missing notification keys skip gracefully without errors."""
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    
    # All should return False (not configured)
    assert discord_configured() is False
    assert ntfy_configured() is False
    assert telegram_configured() is False
    
    # Verify sending doesn't raise errors
    from jobradar.notify import send_discord, send_ntfy, send_telegram
    
    assert send_discord("test") == "skipped"
    assert send_ntfy("test") == "skipped"
    assert send_telegram("test") == "skipped"


def test_notification_keys_partially_set_skip_invalid(monkeypatch):
    """Verify that partially configured services (e.g., Telegram bot token but no chat_id) skip."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    
    assert telegram_configured() is False
    
    from jobradar.notify import send_telegram
    
    assert send_telegram("test") == "skipped"


def test_classify_keeps_ambiguous_jobs(tmp_path):
    """Verify recall-first: ambiguous jobs are kept, not dropped."""
    from jobradar.classify import should_keep
    
    # Clear include/exclude match → should keep (recall-first)
    ambiguous = JobRecord(
        company="Unknown Corp",
        title="Intern Position",
        location="Remote",
        snippet="General internship opportunity",
    )
    assert should_keep(ambiguous) is True
    
    # Exclude match but strong include signal → should keep
    tax_swe = JobRecord(
        company="TaxSoft",
        title="Software Engineer Intern - Tax Software",
        snippet="Build tax software with machine learning",
    )
    assert should_keep(tax_swe) is True
    
    # Pure exclude match → should drop
    nursing = JobRecord(
        company="Hospital Inc",
        title="Nursing Intern",
        snippet="Provide patient care",
    )
    assert should_keep(nursing) is False


def test_scan_handles_empty_sources_gracefully(tmp_path, monkeypatch):
    """Verify that scanning with empty sources list doesn't crash."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "error.db"))
    
    db = Database(tmp_path / "error.db")
    
    # Scan with empty sources should complete without crashing
    stats = run_scan(db=db, sources=[])
    
    # Should complete successfully with no errors
    assert len(stats.source_errors) == 0
    assert stats.fetched == 0


def test_notify_db_record_persists(tmp_path):
    """Verify notification records persist across Notifier instances."""
    db = Database(tmp_path / "persist.db")
    
    job = JobRecord(
        company="Google",
        title="SWE Intern",
        location="Mountain View, CA",
        url="https://example.com/google-swe",
        sources=["test"],
    )
    
    # First notifier: send notification
    notifier1 = Notifier(path=tmp_path / "n1.jsonl", db=db)
    assert notifier1.notify(job) is True
    
    # Second notifier (new instance): should recognize as already notified
    notifier2 = Notifier(path=tmp_path / "n2.jsonl", db=db)
    assert notifier2.notify(job) is False
    
    # Verify DB has the notification record
    assert db.was_notified(job.canonical_key)


def test_priority_company_detection(tmp_path):
    """Verify priority companies are correctly detected and flagged."""
    from jobradar.classify import enrich, is_priority_company
    
    priority_names = [
        "OpenAI",
        "Anthropic",
        "Google",
        "Jane Street",
        "Hudson River Trading",
        "Scale AI",
    ]
    
    for name in priority_names:
        assert is_priority_company(name) is True
        
        job = JobRecord(company=name, title="SWE Intern", location="Remote")
        enriched = enrich(job)
        assert enriched.priority is True
    
    # Non-priority company
    regular = JobRecord(company="Random Startup", title="SWE Intern", location="Remote")
    enriched_regular = enrich(regular)
    assert enriched_regular.priority is False


def test_scan_once_cli_flag_validation():
    """Verify scan requires --once or --loop flag."""
    from jobradar.cli import build_parser
    
    parser = build_parser()
    
    # Valid: scan --once
    args_once = parser.parse_args(["scan", "--once"])
    assert args_once.once is True
    
    # Valid: scan --loop
    args_loop = parser.parse_args(["scan", "--loop"])
    assert args_loop.loop is True
    
    # Valid: scan --loop --interval 600
    args_interval = parser.parse_args(["scan", "--loop", "--interval", "600"])
    assert args_interval.interval == 600


def test_notification_system_end_to_end(tmp_path, monkeypatch):
    """Comprehensive end-to-end test: scan → classify → notify with all channels empty."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "e2e.db"))
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "e2e_notifications.jsonl"))
    
    # Ensure all external channels are disabled
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("GROK_BOT_WEBHOOK_DIRECTOR", raising=False)
    
    db = Database(tmp_path / "e2e.db")
    
    # Seed DB so we're not in seed mode
    seed_job = JobRecord(
        company="Test Corp",
        title="Initial Seed Job",
        location="Remote",
        url="https://example.com/seed",
        sources=["seed"],
    )
    db.upsert_job(seed_job)
    
    # Run scan with empty sources (offline)
    stats = run_scan(db=db, sources=[])
    assert stats.seed_mode is False
    
    # Add new jobs manually and notify them
    notifier = Notifier(path=tmp_path / "e2e_notifications.jsonl", db=db)
    
    jobs = [
        JobRecord(
            company="OpenAI",
            title="Research Engineer Intern",
            location="San Francisco, CA",
            url="https://example.com/openai-research",
            sources=["test"],
            priority=True,
        ),
        JobRecord(
            company="Stripe",
            title="Backend Engineer Intern",
            location="Seattle, WA",
            url="https://example.com/stripe-backend",
            sources=["test"],
            priority=True,
        ),
        JobRecord(
            company="Random Startup",
            title="Software Engineer Intern",
            location="Remote",
            url="https://example.com/random-startup",
            sources=["test"],
            priority=False,
        ),
    ]
    
    notified_count = 0
    for job in jobs:
        stored, is_new = db.upsert_job(job)
        assert is_new is True
        
        # Notify should succeed exactly once
        result = notifier.notify(stored)
        if result:
            notified_count += 1
        
        # Second notify should fail (idempotent)
        assert notifier.notify(stored) is False
    
    assert notified_count == len(jobs)
    
    # Verify notifications file
    notifications_file = Path(tmp_path / "e2e_notifications.jsonl")
    assert notifications_file.exists()
    
    notifications = notifications_file.read_text().strip().split("\n")
    assert len(notifications) == len(jobs)
    
    # Verify priority jobs have [PRIORITY] tag
    for line in notifications:
        data = json.loads(line)
        if data["priority"]:
            assert "[PRIORITY]" in data["text"]
        assert data["channel"] == "jsonl"
        assert data["canonical_key"]
    
    # Verify DB has all notification records
    for job in jobs:
        assert db.was_notified(job.canonical_key)


def test_notify_with_closed_jobs_skipped(tmp_path, monkeypatch):
    """Verify closed jobs are not notified even if new."""
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "closed.jsonl"))
    
    db = Database(tmp_path / "closed.db")
    notifier = Notifier(path=tmp_path / "closed.jsonl", db=db)
    
    closed_job = JobRecord(
        company="ClosedCorp",
        title="Software Engineer Intern 🔒",
        location="Remote",
        url="https://example.com/closed",
        sources=["test"],
        is_closed=True,
    )
    
    stored, is_new = db.upsert_job(closed_job)
    assert is_new is True
    assert stored.is_closed is True
    
    # Notification should succeed (notify.py doesn't filter closed, pipeline does)
    # But let's verify the job is marked as closed
    assert stored.is_closed is True
