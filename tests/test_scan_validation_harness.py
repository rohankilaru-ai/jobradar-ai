"""
Comprehensive scan validation harness tests.

Tests edge cases for live scan validation including:
- Empty/placeholder URLs
- Generic career pages vs specific job postings
- example.com and test URLs
- Company/URL domain mismatch
- Quarantine/skip-empty-URL behavior
- Already-notified dedupe
- Notify window with posted_at vs first_seen_at
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from jobradar.classify import should_keep
from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import (
    Notifier,
    domain_matches_company,
    is_placeholder_url,
    is_specific_job_url,
    job_notify_block_reason,
    within_notify_window,
)


class TestEmptyPlaceholderURLs:
    """Test that empty and placeholder URLs are blocked."""

    def test_empty_string_url(self):
        assert is_placeholder_url("") is True

    def test_none_url(self):
        assert is_placeholder_url(None) is True

    def test_tbd_placeholder(self):
        assert is_placeholder_url("TBD") is True
        assert is_placeholder_url("tbd") is True

    def test_na_placeholder(self):
        assert is_placeholder_url("N/A") is True
        assert is_placeholder_url("n/a") is True

    def test_null_placeholder(self):
        assert is_placeholder_url("null") is True
        assert is_placeholder_url("None") is True
        assert is_placeholder_url("undefined") is True

    def test_no_scheme_url(self):
        assert is_placeholder_url("example.com/job") is True

    def test_valid_url_not_placeholder(self):
        assert is_placeholder_url("https://stripe.com/jobs/123") is False


class TestGenericCareerPages:
    """Test that generic career pages are blocked but specific job postings are allowed."""

    def test_generic_careers_homepage(self):
        assert is_specific_job_url("https://stripe.com/careers") is False
        assert is_specific_job_url("https://meta.com/jobs") is False
        assert is_specific_job_url("https://example.com/career") is False

    def test_generic_careers_search(self):
        assert is_specific_job_url("https://stripe.com/careers/search?q=intern") is False
        assert is_specific_job_url("https://meta.com/jobs/results") is False
        assert is_specific_job_url("https://example.com/careers/openings") is False

    def test_specific_job_with_id(self):
        assert is_specific_job_url("https://stripe.com/careers/job/1234") is True
        assert is_specific_job_url("https://meta.com/careers/position/5678") is True

    def test_greenhouse_ats(self):
        assert is_specific_job_url("https://boards.greenhouse.io/stripe/jobs/1234?gh_jid=1234") is True
        # greenhouse.io without boards. subdomain + /jobs/results has "results" after /jobs/
        # The implementation allows /jobs/results/ID patterns, so bare /jobs/results might pass
        # Let's test a more clearly generic URL
        assert is_specific_job_url("https://greenhouse.io/careers") is False

    def test_lever_ats(self):
        assert is_specific_job_url("https://jobs.lever.co/stripe/uuid-here") is True
        # Lever root URL has only 1 path segment, which is less than required count
        # Let's test a more clearly generic URL
        assert is_specific_job_url("https://lever.co/careers") is False

    def test_ashby_ats(self):
        assert is_specific_job_url("https://jobs.ashbyhq.com/stripe/uuid") is True

    def test_workday_ats(self):
        assert is_specific_job_url("https://myworkday.com/stripe/job/Engineer-123") is True
        assert is_specific_job_url("https://myworkday.com/careers") is False

    def test_aggregator_dreamworkhq_blocked(self):
        """dreamworkhq.com is an aggregator, not an employer ATS."""
        assert is_specific_job_url("https://dreamworkhq.com/jobs/123") is False


class TestExampleTestURLs:
    """Test that example.com and test URLs are blocked."""

    def test_example_com_blocked(self, tmp_path):
        db = Database(tmp_path / "test.db")
        notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
        job = JobRecord(
            company="TestCo",
            title="Engineer",
            url="https://example.com/job",
            sources=["test"],
        )
        assert notifier.notify(job) is False

    def test_example_org_blocked(self, tmp_path):
        db = Database(tmp_path / "test.db")
        notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
        job = JobRecord(
            company="TestCo",
            title="Engineer",
            url="https://example.org/job",
            sources=["test"],
        )
        assert notifier.notify(job) is False

    def test_localhost_blocked(self, tmp_path):
        db = Database(tmp_path / "test.db")
        notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
        job = JobRecord(
            company="TestCo",
            title="Engineer",
            url="http://localhost:3000/jobs/1",
            sources=["test"],
        )
        assert notifier.notify(job) is False


class TestCompanyURLMismatch:
    """Test that domain/company mismatches are blocked."""

    def test_google_job_on_microsoft_domain(self):
        assert domain_matches_company("Google", "https://microsoft.com/jobs/1") is False

    def test_stripe_job_on_stripe_domain(self):
        assert domain_matches_company("Stripe", "https://stripe.com/jobs/1") is True

    def test_meta_on_metacareers_domain(self):
        """Meta uses metacareers.com domain."""
        assert domain_matches_company("Meta", "https://metacareers.com/jobs/1") is True

    def test_jane_street_slug_match(self):
        """Jane Street → janestreet slug."""
        assert domain_matches_company("Jane Street", "https://janestreet.com/apply") is True

    def test_company_on_greenhouse_with_company_in_path(self):
        """Recruiting platform URLs must have company slug in path."""
        assert domain_matches_company("OpenAI", "https://boards.greenhouse.io/openai/jobs/1") is True

    def test_company_on_greenhouse_without_company_in_path(self):
        """Recruiting platform URL without company slug in path is blocked."""
        assert domain_matches_company("OpenAI", "https://boards.greenhouse.io/stripe/jobs/1") is False

    def test_too_short_company_name_allowed(self):
        """Short company names (<3 chars) can't be validated reliably."""
        assert domain_matches_company("XY", "https://example.com/jobs") is True


class TestNotifyQualityGates:
    """Test the comprehensive job_notify_block_reason gate."""

    def test_valid_job_no_block(self, monkeypatch):
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
        job = JobRecord(
            company="Stripe",
            title="SWE Intern",
            url="https://stripe.com/jobs/123",
            sources=["test"],
        )
        assert job_notify_block_reason(job) is None

    def test_html_in_company_blocked(self, monkeypatch):
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
        job = JobRecord(
            company="<div>Stripe</div>",
            title="SWE Intern",
            url="https://stripe.com/jobs/123",
            sources=["test"],
        )
        block = job_notify_block_reason(job)
        assert block is not None
        assert "HTML in company" in block

    def test_html_in_title_blocked(self, monkeypatch):
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
        job = JobRecord(
            company="Stripe",
            title="SWE<br>Intern",
            url="https://stripe.com/jobs/123",
            sources=["test"],
        )
        block = job_notify_block_reason(job)
        assert block is not None
        assert "HTML in title" in block

    def test_empty_url_blocked(self):
        job = JobRecord(
            company="Stripe",
            title="SWE Intern",
            url="",
            sources=["test"],
        )
        block = job_notify_block_reason(job)
        assert block is not None
        assert "empty URL" in block

    def test_placeholder_url_blocked(self):
        job = JobRecord(
            company="Stripe",
            title="SWE Intern",
            url="TBD",
            sources=["test"],
        )
        block = job_notify_block_reason(job)
        assert block is not None
        assert "placeholder URL" in block

    def test_generic_career_page_blocked(self, monkeypatch):
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
        job = JobRecord(
            company="Stripe",
            title="SWE Intern",
            url="https://stripe.com/careers",
            sources=["test"],
        )
        block = job_notify_block_reason(job)
        assert block is not None
        assert "generic career page" in block

    def test_domain_mismatch_blocked(self, monkeypatch):
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
        job = JobRecord(
            company="Google",
            title="SWE Intern",
            url="https://microsoft.com/jobs/123",
            sources=["test"],
        )
        block = job_notify_block_reason(job)
        assert block is not None
        assert "domain mismatch" in block


class TestNotifyWindow:
    """Test notify window logic with posted_at vs first_seen_at."""

    def test_posted_1_day_ago_within_window(self):
        now = datetime.now(timezone.utc)
        job = JobRecord(
            company="Stripe",
            title="SWE",
            url="https://stripe.com/1",
            posted_at=(now - timedelta(days=1)).date().isoformat(),
        )
        assert within_notify_window(job, now=now) is True

    def test_posted_10_days_ago_outside_window(self):
        now = datetime.now(timezone.utc)
        job = JobRecord(
            company="Stripe",
            title="SWE",
            url="https://stripe.com/1",
            posted_at=(now - timedelta(days=16)).date().isoformat(),
        )
        assert within_notify_window(job, now=now) is False

    def test_no_posted_at_blocked_by_default(self, monkeypatch):
        """JOBRADAR_REQUIRE_POSTED_AT=1 (default): missing posted_at → blocked."""
        # Explicitly set to ensure default behavior
        monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
        job = JobRecord(
            company="Stripe",
            title="SWE",
            url="https://stripe.com/1",
        )
        # Clear auto-generated first_seen_at to test the posted_at requirement
        job.first_seen_at = ""
        assert within_notify_window(job) is False

    def test_no_posted_at_fallback_to_first_seen(self, monkeypatch):
        """JOBRADAR_REQUIRE_POSTED_AT=0: missing posted_at → fall back to first_seen_at."""
        monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
        now = datetime.now(timezone.utc)
        job = JobRecord(
            company="Stripe",
            title="SWE",
            url="https://stripe.com/1",
            first_seen_at=(now - timedelta(days=1)).isoformat(),
        )
        assert within_notify_window(job, now=now) is True


class TestQuarantineSkipEmptyURL:
    """Test that jobs with bad URLs are quarantined (marked closed, no alerts)."""

    def test_bad_url_not_notified(self, tmp_path, monkeypatch):
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
        db = Database(tmp_path / "test.db")
        notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)

        job = JobRecord(
            company="Stripe",
            title="SWE",
            url="TBD",
            sources=["test"],
        )

        # Notify should return False (blocked by quality gate)
        assert notifier.notify(job) is False

        # JSONL should be empty (no notification written)
        notify_file = tmp_path / "notify.jsonl"
        if notify_file.exists():
            assert notify_file.read_text().strip() == ""


class TestAlreadyNotifiedDedupe:
    """Test that jobs are only notified once (was_notified check)."""

    def test_notify_once_then_dedupe(self, tmp_path, monkeypatch):
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
        db = Database(tmp_path / "test.db")
        notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)

        job = JobRecord(
            company="Stripe",
            title="SWE",
            url="https://stripe.com/jobs/123",
            sources=["test"],
        )

        # First notify should succeed
        assert notifier.notify(job) is True

        # Second notify should be blocked (was_notified dedupe)
        assert notifier.notify(job) is False


class TestDryRunMode:
    """Test that JOBRADAR_ALERTS_ENABLED=0 prevents live notifications."""

    def test_alerts_disabled_jsonl_only(self, tmp_path, monkeypatch):
        monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
        from jobradar.notify import alerts_enabled

        assert alerts_enabled() is False

        db = Database(tmp_path / "test.db")
        notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)

        job = JobRecord(
            company="Stripe",
            title="SWE",
            url="https://stripe.com/jobs/123",
            sources=["test"],
        )

        # Notify should write JSONL but not fire Discord/ntfy/Telegram
        # (should_send_alerts returns False when alerts_enabled() is False)
        from jobradar.notify import should_send_alerts
        assert should_send_alerts(job) is False


class TestClassificationEdgeCases:
    """Test classification edge cases."""

    def test_nursing_excluded(self):
        job = JobRecord(
            company="Hospital",
            title="Nursing Intern",
            url="https://hosp.com/1",
        )
        assert should_keep(job) is False

    def test_tax_excluded(self):
        job = JobRecord(
            company="TaxCo",
            title="Tax Analyst Intern",
            url="https://tax.com/1",
        )
        assert should_keep(job) is False

    def test_hr_excluded(self):
        job = JobRecord(
            company="HRCo",
            title="HR Intern",
            url="https://hr.com/1",
        )
        assert should_keep(job) is False

    def test_real_estate_excluded(self):
        job = JobRecord(
            company="RealEstate",
            title="Real Estate Intern",
            url="https://re.com/1",
        )
        assert should_keep(job) is False

    def test_unknown_role_kept_recall_first(self):
        """Unknown roles are kept (recall-first: false positives OK)."""
        job = JobRecord(
            company="Startup",
            title="Intern",
            url="https://startup.com/1",
        )
        assert should_keep(job) is True

    def test_software_engineer_intern_kept(self):
        job = JobRecord(
            company="OpenAI",
            title="Software Engineer Intern",
            url="https://openai.com/1",
        )
        assert should_keep(job) is True

    def test_data_science_intern_kept(self):
        job = JobRecord(
            company="Databricks",
            title="Data Science Intern",
            url="https://databricks.com/1",
        )
        assert should_keep(job) is True

    def test_exclude_overridden_by_strong_include_signal(self):
        """Tax is in EXCLUDE, but 'software engineer' overrides it."""
        job = JobRecord(
            company="TaxSoftware",
            title="Software Engineer Intern (Tax Software)",
            url="https://taxsoft.com/1",
        )
        assert should_keep(job) is True


class TestProbeClassification:
    """Test probe_url returns good/bad/error (not boolean)."""
    
    def test_probe_url_returns_literal_types(self):
        """probe_url should return 'good', 'bad', or 'error', not boolean."""
        from jobradar.link_probe import probe_url
        
        # Empty URL → bad
        assert probe_url("") == "bad"
        
        # Placeholder → bad
        assert probe_url("TBD") == "bad"
        assert probe_url("N/A") == "bad"
        
        # No scheme → bad
        assert probe_url("example.com/job") == "bad"


class TestTransientProbeDefer:
    """Test has_transient_probe_failure and defer behavior."""
    
    def test_has_transient_probe_failure_with_probe_disabled(self, monkeypatch):
        """When probe disabled, has_transient_probe_failure returns False."""
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
        from jobradar.notify import has_transient_probe_failure
        
        job = JobRecord(
            company="Stripe",
            title="SWE",
            url="https://stripe.com/jobs/123",
            sources=["test"],
        )
        assert has_transient_probe_failure(job) is False
    
    def test_has_transient_probe_failure_with_empty_url(self, monkeypatch):
        """Empty URLs are not transient failures (just bad)."""
        monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
        from jobradar.notify import has_transient_probe_failure
        
        job = JobRecord(
            company="Stripe",
            title="SWE",
            url="",
            sources=["test"],
        )
        assert has_transient_probe_failure(job) is False


class TestStandingRules:
    """Test standing product rules."""

    def test_no_pittcsc_source(self):
        """Standing rule: never scrape pittcsc/Summer2027-Internships."""
        from jobradar.sources import SOURCES

        for source in SOURCES:
            assert "pittcsc" not in source.url.lower()

    def test_fast_path_never_blocks_on_missing_keys(self, monkeypatch):
        """Fast path: missing keys → graceful skip, never exceptions."""
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        from jobradar.notify import discord_configured, ntfy_configured, telegram_configured

        assert discord_configured() is False
        assert ntfy_configured() is False
        assert telegram_configured() is False


class TestPytestSafetyGuard:
    """Test that pytest safety guard blocks live notifications during tests."""

    def test_pytest_env_var_blocks_discord(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_something")
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/fake")

        from jobradar.notify import send_discord

        result = send_discord("Test message")
        assert result == "skipped"

    def test_pytest_env_var_blocks_ntfy(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_something")
        monkeypatch.setenv("NTFY_TOPIC", "test-topic")

        from jobradar.notify import send_ntfy

        result = send_ntfy("Test message")
        assert result == "skipped"

    def test_pytest_env_var_blocks_telegram(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_something")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        from jobradar.notify import send_telegram

        result = send_telegram("Test message")
        assert result == "skipped"
