"""Tests for transient probe failure deferral (overnight #21).

Ensures transient failures (timeout, 5xx, connection error) defer without
marking was_notified, while hard failures (empty URL, example.com, 404) stay
permanently blocked.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import (
    Notifier,
    has_transient_probe_failure,
    job_notify_block_reason,
)
from jobradar.pipeline import run_scan


def test_transient_probe_failure_detected_timeout(monkeypatch, respx_mock):
    """Timeout is detected as transient failure."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    # Mock timeout on Greenhouse (use company name matching the URL path)
    respx_mock.head("https://boards.greenhouse.io/stripe/jobs/12345").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    
    job = JobRecord(
        company="Stripe",
        title="SWE Intern",
        url="https://boards.greenhouse.io/stripe/jobs/12345",
        sources=["test"],
    )
    
    # Should be detected as transient
    assert has_transient_probe_failure(job) is True
    # Should NOT be a hard block
    assert job_notify_block_reason(job) is None


def test_transient_probe_failure_detected_5xx(monkeypatch, respx_mock):
    """5xx errors are detected as transient failures."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    # Mock 500 error on Lever (use company name matching the URL path)
    respx_mock.head("https://jobs.lever.co/databricks/engineer").mock(
        return_value=httpx.Response(500)
    )
    
    job = JobRecord(
        company="Databricks",
        title="ML Intern",
        url="https://jobs.lever.co/databricks/engineer",
        sources=["test"],
    )
    
    # Should be detected as transient
    assert has_transient_probe_failure(job) is True
    # Should NOT be a hard block
    assert job_notify_block_reason(job) is None


def test_transient_probe_failure_detected_connection_error(monkeypatch, respx_mock):
    """Connection errors are detected as transient failures."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    # Mock connection error on Ashby
    respx_mock.head("https://jobs.ashbyhq.com/anthropic/job123").mock(
        side_effect=httpx.ConnectError("connection failed")
    )
    
    job = JobRecord(
        company="Anthropic",
        title="Research Intern",
        url="https://jobs.ashbyhq.com/anthropic/job123",
        sources=["test"],
    )
    
    # Should be detected as transient
    assert has_transient_probe_failure(job) is True
    # Should NOT be a hard block
    assert job_notify_block_reason(job) is None


def test_hard_failure_404_is_permanent_block(monkeypatch, respx_mock):
    """404 errors are hard failures, permanently blocked."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    # Mock 404 on recruiting platform
    respx_mock.head("https://boards.greenhouse.io/roblox/jobs/404").mock(
        return_value=httpx.Response(404)
    )
    
    job = JobRecord(
        company="Roblox",
        title="Engineer",
        url="https://boards.greenhouse.io/roblox/jobs/404",
        sources=["test"],
    )
    
    # Should NOT be transient
    assert has_transient_probe_failure(job) is False
    # Should be a hard block
    reason = job_notify_block_reason(job)
    assert reason is not None
    assert "probe failed (hard)" in reason


def test_hard_failure_empty_url(monkeypatch):
    """Empty URLs are hard failures, permanently blocked."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    job = JobRecord(
        company="NoURL",
        title="Intern",
        url="",
        sources=["test"],
    )
    
    # Should NOT be transient
    assert has_transient_probe_failure(job) is False
    # Should be a hard block
    reason = job_notify_block_reason(job)
    assert reason is not None
    assert "empty URL" in reason


def test_hard_failure_placeholder_url(monkeypatch):
    """Placeholder URLs (TBD, N/A) are hard failures, permanently blocked."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    job = JobRecord(
        company="TBDCo",
        title="Intern",
        url="TBD",
        sources=["test"],
    )
    
    # Should NOT be transient
    assert has_transient_probe_failure(job) is False
    # Should be a hard block
    reason = job_notify_block_reason(job)
    assert reason is not None
    assert "placeholder URL" in reason


def test_hard_failure_example_com(monkeypatch):
    """example.com URLs are hard failures, permanently blocked."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    job = JobRecord(
        company="ExampleCo",
        title="Intern",
        url="https://example.com/job",
        sources=["test"],
    )
    
    # Should NOT be transient
    assert has_transient_probe_failure(job) is False
    # Should be a hard block
    reason = job_notify_block_reason(job)
    assert reason is not None
    assert "example.com" in reason


def test_transient_failure_does_not_mark_notified(tmp_path, monkeypatch, respx_mock):
    """Transient probe failure: writes JSONL but does NOT mark was_notified."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    # Mock timeout on Greenhouse
    respx_mock.head("https://boards.greenhouse.io/openai/jobs/123").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="OpenAI",
        title="SWE Intern",
        url="https://boards.greenhouse.io/openai/jobs/123",
        sources=["test"],
    )
    
    # Notify with silent=False (would normally alert)
    # But transient failure should defer (write JSONL, no live alerts, no mark notified)
    with patch("jobradar.notify.send_discord") as mock_discord:
        with patch("jobradar.notify.send_ntfy") as mock_ntfy:
            with patch("jobradar.notify.send_telegram") as mock_telegram:
                result = notifier.notify(job, silent=False)
                
                # Should return True (processed/deferred)
                assert result is True
                
                # Should NOT send live alerts
                mock_discord.assert_not_called()
                mock_ntfy.assert_not_called()
                mock_telegram.assert_not_called()
    
    # Should NOT be marked as notified (allows retry)
    assert db.was_notified(job.canonical_key) is False
    
    # Should have written to JSONL
    jsonl_path = tmp_path / "notify.jsonl"
    assert jsonl_path.exists()
    lines = jsonl_path.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["canonical_key"] == job.canonical_key
    assert record["silent"] is True  # Forced silent due to defer
    assert record["deferred"] is True  # Marked as deferred


def test_transient_failure_allows_retry_after_recovery(tmp_path, monkeypatch, respx_mock):
    """After transient failure, job can alert once URL recovers."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="Meta",
        title="ML Intern",
        url="https://jobs.lever.co/meta/ml-intern",
        sources=["test"],
    )
    
    # First scan: timeout (transient failure)
    respx_mock.head("https://jobs.lever.co/meta/ml-intern").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    
    with patch("jobradar.notify.send_discord"):
        with patch("jobradar.notify.send_ntfy"):
            with patch("jobradar.notify.send_telegram"):
                result1 = notifier.notify(job, silent=False)
                assert result1 is True
    
    # Should NOT be marked as notified
    assert db.was_notified(job.canonical_key) is False
    
    # Second scan: URL recovers (200 OK)
    respx_mock.clear()
    respx_mock.head("https://jobs.lever.co/meta/ml-intern").mock(
        return_value=httpx.Response(200)
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord:
        with patch("jobradar.notify.send_ntfy") as mock_ntfy:
            with patch("jobradar.notify.send_telegram") as mock_telegram:
                result2 = notifier.notify(job, silent=False)
                assert result2 is True
                
                # Should send live alerts this time
                mock_discord.assert_called_once()
                mock_ntfy.assert_called_once()
                mock_telegram.assert_called_once()
    
    # NOW should be marked as notified
    assert db.was_notified(job.canonical_key) is True
    
    # Third scan: should not alert again (already notified)
    respx_mock.clear()
    respx_mock.head("https://jobs.lever.co/meta/ml-intern").mock(
        return_value=httpx.Response(200)
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord:
        result3 = notifier.notify(job, silent=False)
        assert result3 is False  # Already notified
        mock_discord.assert_not_called()


def test_hard_failure_never_alerts(tmp_path, monkeypatch, respx_mock):
    """Hard failures (404, empty URL, example.com) never alert, even after retries."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    # Test 404
    job_404 = JobRecord(
        company="Dead404",
        title="Intern",
        url="https://boards.greenhouse.io/dead/jobs/404",
        sources=["test"],
    )
    respx_mock.head("https://boards.greenhouse.io/dead/jobs/404").mock(
        return_value=httpx.Response(404)
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord:
        result = notifier.notify(job_404, silent=False)
        assert result is False  # Blocked
        mock_discord.assert_not_called()
    
    # Test empty URL
    job_empty = JobRecord(
        company="EmptyCo",
        title="Intern",
        url="",
        sources=["test"],
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord:
        result = notifier.notify(job_empty, silent=False)
        assert result is False  # Blocked
        mock_discord.assert_not_called()
    
    # Test example.com
    job_example = JobRecord(
        company="ExampleCo",
        title="Intern",
        url="https://example.com/job",
        sources=["test"],
    )
    
    with patch("jobradar.notify.send_discord") as mock_discord:
        result = notifier.notify(job_example, silent=False)
        assert result is False  # Blocked
        mock_discord.assert_not_called()


def test_successful_alert_marks_notified(tmp_path, monkeypatch, respx_mock):
    """Successful alert marks was_notified and prevents double-alert."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="GoodCo",
        title="Engineer",
        url="https://boards.greenhouse.io/goodco/jobs/12345",
        sources=["test"],
    )
    
    # Mock successful probe
    respx_mock.head("https://boards.greenhouse.io/goodco/jobs/12345").mock(
        return_value=httpx.Response(200)
    )
    
    # First notification should succeed
    with patch("jobradar.notify.send_discord") as mock_discord:
        with patch("jobradar.notify.send_ntfy") as mock_ntfy:
            with patch("jobradar.notify.send_telegram") as mock_telegram:
                result = notifier.notify(job, silent=False)
                assert result is True
                mock_discord.assert_called_once()
                mock_ntfy.assert_called_once()
                mock_telegram.assert_called_once()
    
    # Should be marked as notified
    assert db.was_notified(job.canonical_key) is True
    
    # Second notification should be blocked (already notified)
    with patch("jobradar.notify.send_discord") as mock_discord:
        result = notifier.notify(job, silent=False)
        assert result is False
        mock_discord.assert_not_called()


def test_probe_disabled_preserves_test_mode(tmp_path, monkeypatch):
    """With JOBRADAR_LINK_PROBE=0, probing is bypassed (test mode)."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="TestCo",
        title="Intern",
        url="https://boards.greenhouse.io/testco/jobs/123",
        sources=["test"],
    )
    
    # Should NOT detect as transient (probe disabled)
    assert has_transient_probe_failure(job) is False
    
    # Should pass quality gates (probe disabled)
    assert job_notify_block_reason(job) is None
    
    # Should notify successfully
    with patch("jobradar.notify.send_discord") as mock_discord:
        result = notifier.notify(job, silent=False)
        assert result is True
        mock_discord.assert_called_once()
    
    # Should mark as notified
    assert db.was_notified(job.canonical_key) is True


def test_pipeline_tracks_probe_deferred_stat(tmp_path, monkeypatch, respx_mock):
    """Pipeline tracks probe_deferred stat for transient failures."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notify.jsonl"))
    
    job = JobRecord(
        company="Google",
        title="SWE Intern",
        url="https://boards.greenhouse.io/google/jobs/123",
        sources=["mock"],
        posted_at="2026-09-20",  # Within window
    )
    
    # Mock timeout for the job URL
    respx_mock.head("https://boards.greenhouse.io/google/jobs/123").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    
    # Directly mock scout_all instead of trying to mock HTTP sources
    with patch("jobradar.pipeline.scout_all") as mock_scout:
        from jobradar.scout import ScoutResult
        mock_scout.return_value = [
            ScoutResult(
                source="mock",
                jobs=[job],
                error=None,
                not_modified=False,
            )
        ]
        
        db = Database(tmp_path / "test.db")
        # Use alert_all=True to avoid seed mode
        stats = run_scan(db=db, alert_all=True)
    
    # Should have processed the job
    assert stats.fetched == 1
    assert stats.kept == 1
    assert stats.new == 1
    assert stats.notified == 1
    
    # Should have tracked the deferral
    assert stats.probe_deferred == 1
    
    # Should NOT have alerted
    assert stats.alerted == 0
    
    # Should NOT be marked as notified in DB
    assert db.was_notified(job.canonical_key) is False
