"""Tests for bad URL detection and quarantine."""

from unittest.mock import Mock, patch

import httpx
import pytest

from jobradar.db import Database
from jobradar.models import JobRecord, is_bad_url
from jobradar.pipeline import run_scan


def test_is_bad_url_empty():
    assert is_bad_url("") is True
    assert is_bad_url("   ") is True
    assert is_bad_url(None) is True


def test_is_bad_url_placeholders():
    assert is_bad_url("http://example.com") is True
    assert is_bad_url("https://example.com/jobs") is True
    assert is_bad_url("http://test.com") is True
    assert is_bad_url("http://localhost:3000") is True
    assert is_bad_url("http://127.0.0.1:8080") is True
    assert is_bad_url("about:blank") is True
    assert is_bad_url("javascript:alert(1)") is True
    assert is_bad_url("mailto:test@example.com") is True


def test_is_bad_url_valid():
    assert is_bad_url("https://stripe.com/jobs") is False
    assert is_bad_url("https://openai.com/careers") is False
    assert is_bad_url("https://jobs.lever.co/stripe/123") is False


def test_is_bad_url_malformed():
    assert is_bad_url("not-a-url") is True
    assert is_bad_url("htp:/missing-slash") is True
    assert is_bad_url("//no-scheme.com") is True


def test_pipeline_skips_bad_urls(tmp_path, monkeypatch):
    """Pipeline should skip jobs with bad URLs at ingest."""
    from jobradar.sources import Source

    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")

    # Mock scout_all to return jobs with both good and bad URLs
    mock_jobs = [
        JobRecord(
            company="GoodCo",
            title="SWE Intern",
            location="SF",
            url="https://goodco.com/jobs/123",
            sources=["test"],
        ),
        JobRecord(
            company="BadCo",
            title="SWE Intern",
            location="NYC",
            url="http://example.com",
            sources=["test"],
        ),
        JobRecord(
            company="EmptyCo",
            title="SWE Intern",
            location="Remote",
            url="",
            sources=["test"],
        ),
    ]

    from jobradar.scout import ScoutResult

    with patch("jobradar.pipeline.scout_all") as mock_scout:
        mock_scout.return_value = [
            ScoutResult(source="test", jobs=mock_jobs, error=None, not_modified=False)
        ]

        db = Database(tmp_path / "test.db")
        stats = run_scan(db=db, sources=[], alert_all=False)

        assert stats.fetched == 3
        assert stats.kept == 3
        assert stats.skipped_bad_url == 2
        assert stats.new == 1
        assert db.count_jobs() == 1

        stored = db.get_job(mock_jobs[0].canonical_key)
        assert stored is not None
        assert stored.company == "GoodCo"


def test_quarantine_cli_marks_bad_urls(tmp_path, monkeypatch, capsys):
    """Quarantine CLI should mark existing jobs with bad URLs as closed."""
    from jobradar.cli import cmd_quarantine_bad_urls

    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")

    db = Database(tmp_path / "test.db")

    # Insert jobs with good and bad URLs
    good_job = JobRecord(
        company="GoodCo",
        title="SWE Intern",
        location="SF",
        url="https://goodco.com/jobs/123",
    )
    bad_job = JobRecord(
        company="BadCo",
        title="SWE Intern",
        location="NYC",
        url="http://example.com",
    )
    empty_job = JobRecord(
        company="EmptyCo",
        title="SWE Intern",
        location="Remote",
        url="",
    )

    db.upsert_job(good_job)
    db.upsert_job(bad_job)
    db.upsert_job(empty_job)

    assert db.count_jobs() == 3

    args = Mock()
    with patch("jobradar.cli.Database") as mock_db_cls:
        mock_db_cls.return_value = db
        result = cmd_quarantine_bad_urls(args)

    assert result == 0

    captured = capsys.readouterr()
    assert "checked=3" in captured.out
    assert "quarantined=2" in captured.out
    assert "already_ok=1" in captured.out

    # Verify bad jobs are closed
    bad_stored = db.get_job(bad_job.canonical_key)
    assert bad_stored.is_closed is True
    empty_stored = db.get_job(empty_job.canonical_key)
    assert empty_stored.is_closed is True

    # Good job should not be closed
    good_stored = db.get_job(good_job.canonical_key)
    assert good_stored.is_closed is False


def test_quarantine_cli_with_probe(tmp_path, monkeypatch, capsys):
    """Quarantine CLI with JOBRADAR_LINK_PROBE=1 should probe URLs."""
    from jobradar.cli import cmd_quarantine_bad_urls

    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")

    db = Database(tmp_path / "test.db")

    # Insert job with URL that will fail probe
    failing_job = JobRecord(
        company="FailCo",
        title="SWE Intern",
        location="SF",
        url="https://failco.com/404",
    )
    success_job = JobRecord(
        company="SuccessCo",
        title="SWE Intern",
        location="NYC",
        url="https://successco.com/jobs",
    )

    db.upsert_job(failing_job)
    db.upsert_job(success_job)

    args = Mock()

    # Mock httpx.head to simulate probe results
    def mock_head(url, **kwargs):
        mock_resp = Mock()
        if "404" in url:
            mock_resp.status_code = 404
        else:
            mock_resp.status_code = 200
        return mock_resp

    with patch("jobradar.cli.Database") as mock_db_cls:
        mock_db_cls.return_value = db
        with patch("httpx.head", side_effect=mock_head):
            result = cmd_quarantine_bad_urls(args)

    assert result == 0

    captured = capsys.readouterr()
    assert "checked=2" in captured.out
    assert "quarantined=1" in captured.out

    # Failing job should be closed
    failing_stored = db.get_job(failing_job.canonical_key)
    assert failing_stored.is_closed is True

    # Success job should not be closed
    success_stored = db.get_job(success_job.canonical_key)
    assert success_stored.is_closed is False


def test_quarantine_does_not_notify(tmp_path, monkeypatch):
    """Quarantine should never send notifications."""
    from jobradar.cli import cmd_quarantine_bad_urls

    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")

    db = Database(tmp_path / "test.db")
    bad_job = JobRecord(
        company="BadCo",
        title="SWE Intern",
        url="http://example.com",
    )
    db.upsert_job(bad_job)

    args = Mock()

    # Mock notifiers to ensure they're never called
    with patch("jobradar.cli.Database") as mock_db_cls:
        mock_db_cls.return_value = db
        with patch("jobradar.notify.send_discord") as mock_discord, \
             patch("jobradar.notify.send_ntfy") as mock_ntfy, \
             patch("jobradar.notify.send_telegram") as mock_telegram:

            cmd_quarantine_bad_urls(args)

            # Verify no notifications were sent
            mock_discord.assert_not_called()
            mock_ntfy.assert_not_called()
            mock_telegram.assert_not_called()


def test_quarantine_does_not_enqueue_grok(tmp_path, monkeypatch):
    """Quarantine should never enqueue Grok/Director."""
    from jobradar.cli import cmd_quarantine_bad_urls

    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")

    db = Database(tmp_path / "test.db")
    bad_job = JobRecord(
        company="BadCo",
        title="SWE Intern",
        url="http://example.com",
    )
    db.upsert_job(bad_job)

    args = Mock()

    with patch("jobradar.cli.Database") as mock_db_cls:
        mock_db_cls.return_value = db
        with patch("jobradar.director.enqueue") as mock_enqueue:
            cmd_quarantine_bad_urls(args)
            mock_enqueue.assert_not_called()
