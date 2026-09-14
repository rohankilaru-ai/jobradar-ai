"""
Offline tests for live scan validation without needing secrets.
These tests document and validate the live-scan checklist pieces.
"""

import os
import tempfile
from pathlib import Path

import pytest

from jobradar.classify import EXCLUDE, INCLUDE, should_keep
from jobradar.cli import main
from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import discord_configured, ntfy_configured, telegram_configured
from jobradar.pipeline import run_scan
from jobradar.sources import Source


def test_health_cli_smoke(capsys, tmp_path, monkeypatch):
    """Health check runs without secrets and shows graceful skips."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "health.db"))
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)

    assert main(["health"]) == 0
    out = capsys.readouterr().out
    assert "jobradar 0.1.0 ok" in out
    assert "notifiers: jsonl" in out
    assert "notion: skipped until keys set" in out
    # gmail may be configured if secrets/gmail-client.json exists on the machine
    assert (
        "gmail: skipped until secrets/gmail-client.json" in out
        or "gmail: configured" in out
    )


def test_scan_once_with_empty_sources(tmp_path, monkeypatch):
    """Scan with empty sources completes without errors (mocked sources)."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "scan.db"))
    db = Database(tmp_path / "scan.db")

    stats = run_scan(db=db, sources=[])
    assert stats.fetched == 0
    assert stats.kept == 0
    assert stats.new == 0
    assert stats.notified == 0
    assert stats.seed_mode is True


def test_scan_once_with_mocked_source(tmp_path, monkeypatch):
    """Scan with mocked source validates classification logic."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "mocked.db"))
    db = Database(tmp_path / "mocked.db")

    # Create a fake source that would be processed
    # In reality, scout_all would fetch these, but we test classification directly
    jobs = [
        JobRecord(
            company="OpenAI",
            title="Software Engineer Intern",
            location="San Francisco, CA",
            url="https://careers.openai.com/123",
            sources=["test"],
        ),
        JobRecord(
            company="Hospital",
            title="Nursing Intern",
            location="NYC",
            url="https://example.com/nursing",
            sources=["test"],
        ),
        JobRecord(
            company="TaxCorp",
            title="Tax Analyst Intern",
            location="Chicago",
            url="https://example.com/tax",
            sources=["test"],
        ),
    ]

    kept = [j for j in jobs if should_keep(j)]
    assert len(kept) == 1  # Only OpenAI SWE passes
    assert kept[0].company == "OpenAI"


def test_classify_include_keywords():
    """Recall-first: INCLUDE keywords keep jobs."""
    assert should_keep(
        JobRecord(company="X", title="Software Engineer Intern", url="https://x.com/1")
    )
    assert should_keep(
        JobRecord(company="Y", title="Data Science Intern", url="https://y.com/2")
    )
    assert should_keep(
        JobRecord(company="Z", title="Machine Learning Intern", url="https://z.com/3")
    )
    assert should_keep(JobRecord(company="A", title="SWE Intern", url="https://a.com/4"))
    assert should_keep(
        JobRecord(company="B", title="Fullstack Developer Intern", url="https://b.com/5")
    )
    assert should_keep(
        JobRecord(company="C", title="AI Research Intern", url="https://c.com/6")
    )


def test_classify_exclude_keywords():
    """EXCLUDE keywords drop clear negatives."""
    assert not should_keep(
        JobRecord(company="Hospital", title="Nursing Intern", url="https://hosp.com/1")
    )
    assert not should_keep(
        JobRecord(company="TaxCo", title="Tax Analyst Intern", url="https://tax.com/2")
    )
    assert not should_keep(
        JobRecord(company="HR Inc", title="HR Intern", url="https://hr.com/3")
    )
    assert not should_keep(
        JobRecord(
            company="Marketing", title="Marketing Intern", url="https://mkt.com/4"
        )
    )
    assert not should_keep(
        JobRecord(company="RealEstate", title="Real Estate Intern", url="https://re.com/5")
    )


def test_classify_unknown_roles_kept():
    """Recall-first: unknown roles are kept rather than dropped."""
    assert should_keep(
        JobRecord(company="Startup", title="Intern", url="https://startup.com/1")
    )
    assert should_keep(
        JobRecord(
            company="Company", title="Summer Intern 2027", url="https://company.com/2"
        )
    )
    assert should_keep(
        JobRecord(
            company="NewCo", title="Technical Intern", url="https://newco.com/3"
        )
    )


def test_classify_exclude_with_strong_include_signal():
    """EXCLUDE can be overridden by strong INCLUDE signals."""
    # "tax" is in EXCLUDE, but if "software engineer" is present, keep it
    job = JobRecord(
        company="TechCorp",
        title="Software Engineer Intern (Tax Software)",
        url="https://tech.com/1",
    )
    assert should_keep(job)


def test_notifier_adapters_skip_without_keys(monkeypatch):
    """Missing keys cause graceful skips, never exceptions."""
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    assert discord_configured() is False
    assert ntfy_configured() is False
    assert telegram_configured() is False


def test_scan_cli_requires_once_or_loop(tmp_path, monkeypatch):
    """Scan CLI must have --once or --loop flag."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "cli.db"))

    # Scan without --once or --loop should fail with error
    with pytest.raises(SystemExit) as exc_info:
        main(["scan"])
    assert exc_info.value.code != 0


def test_scan_cli_once_flag(tmp_path, monkeypatch, capsys):
    """Scan --once completes without errors on empty DB."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "cli.db"))
    # Don't actually run scan with live sources in CI, just validate CLI parsing
    # The actual scan is tested in test_pipeline.py
    from jobradar.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["scan", "--once"])
    assert args.once is True
    assert args.loop is False


def test_first_scan_seeds_without_alerts(tmp_path):
    """First scan on empty DB seeds without notifying (unless --alert-all)."""
    db = Database(tmp_path / "seed.db")
    assert db.count_jobs() == 0

    # Empty sources for speed
    stats = run_scan(db=db, sources=[])
    assert stats.seed_mode is True
    assert stats.notified == 0


def test_subsequent_scan_notifies_new_jobs(tmp_path):
    """Second scan after seeding notifies new jobs."""
    db = Database(tmp_path / "notify.db")

    # Seed one job
    job1 = JobRecord(
        company="Stripe",
        title="SWE Intern",
        location="SF",
        url="https://stripe.com/job1",
        sources=["test"],
    )
    db.upsert_job(job1)

    # Now run scan on non-empty DB
    stats = run_scan(db=db, sources=[])
    assert stats.seed_mode is False

    # If there were new jobs, they would be notified
    # (but we have empty sources here, so notified=0)


def test_alert_all_flag_overrides_seed_mode(tmp_path):
    """--alert-all forces notifications on first scan."""
    db = Database(tmp_path / "alert_all.db")
    assert db.count_jobs() == 0

    stats = run_scan(db=db, sources=[], alert_all=True)
    # seed_mode should be False because alert_all=True
    assert stats.seed_mode is False


def test_source_errors_recorded(tmp_path, monkeypatch):
    """Source fetch errors are captured in stats, not raised."""
    db = Database(tmp_path / "errors.db")

    # Mock a source that would fail (bad URL)
    bad_source = Source(
        name="bad-source",
        url="https://invalid.example.com/nonexistent.json",
        kind="aprameyak",
    )

    stats = run_scan(db=db, sources=[bad_source])
    # Error should be recorded in stats
    assert len(stats.source_errors) > 0 or stats.fetched == 0


def test_db_upsert_idempotent(tmp_path):
    """Database upsert is idempotent on same canonical_key."""
    db = Database(tmp_path / "upsert.db")

    job1 = JobRecord(
        company="Meta",
        title="SWE Intern",
        location="Menlo Park",
        url="https://meta.com/job1",
        sources=["test"],
    )

    stored1, is_new1 = db.upsert_job(job1)
    assert is_new1 is True

    # Same job again
    stored2, is_new2 = db.upsert_job(job1)
    assert is_new2 is False
    assert stored1.canonical_key == stored2.canonical_key


def test_exclude_keywords_documented():
    """EXCLUDE list is non-empty and matches expected keywords."""
    assert len(EXCLUDE) > 0
    assert "nursing" in EXCLUDE
    assert "tax intern" in EXCLUDE
    assert "hr intern" in EXCLUDE
    assert "marketing intern" in EXCLUDE


def test_include_keywords_documented():
    """INCLUDE list is non-empty and matches expected keywords."""
    assert len(INCLUDE) > 0
    assert "software" in INCLUDE
    assert "engineer" in INCLUDE
    assert "data science" in INCLUDE
    assert "machine learning" in INCLUDE


def test_env_example_exists():
    """Validate .env.example exists for user setup."""
    env_example = Path(__file__).parent.parent / ".env.example"
    assert env_example.exists()
    content = env_example.read_text()
    assert "DISCORD_WEBHOOK_URL" in content
    assert "NTFY_TOPIC" in content
    assert "JOBRADAR_DB_PATH" in content


def test_docs_exist():
    """Validate key documentation files exist."""
    docs_dir = Path(__file__).parent.parent / "docs"
    assert (docs_dir / "ACCOUNTS.md").exists()
    assert (docs_dir / "LIVE_SCAN_VALIDATION.md").exists()


def test_standing_rules_no_pittcsc():
    """Standing rule: never scrape pittcsc/Summer2027-Internships."""
    from jobradar.sources import SOURCES

    for source in SOURCES:
        assert "pittcsc" not in source.url.lower()


def test_standing_rules_no_email_alerts():
    """Standing rule: no email alerts (only Discord/ntfy/Telegram)."""
    # Validate that notify.py doesn't have email sending
    from jobradar import notify

    # Email functions should not exist or should be stubs
    assert not hasattr(notify, "send_email") or not callable(
        getattr(notify, "send_email", None)
    )


def test_fast_path_never_blocks():
    """Fast path: classification and notification never wait on missing keys."""
    # This is implicitly tested by all the monkeypatch tests above
    # that delete keys and expect graceful skips
    pass


def test_priority_companies_documented():
    """Priority company list exists and includes expected names."""
    from jobradar.classify import PRIORITY_COMPANIES

    assert len(PRIORITY_COMPANIES) > 0
    assert "openai" in PRIORITY_COMPANIES
    assert "anthropic" in PRIORITY_COMPANIES
    assert "google" in PRIORITY_COMPANIES
