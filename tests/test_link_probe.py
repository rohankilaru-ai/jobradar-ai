"""Tests for link probe and verify-links CLI."""

import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from jobradar.db import Database
from jobradar.link_probe import is_placeholder_url, probe_url
from jobradar.models import JobRecord
from jobradar.notify import Notifier


def test_is_placeholder_url():
    assert is_placeholder_url("") is True
    assert is_placeholder_url("TBD") is True
    assert is_placeholder_url("N/A") is True
    assert is_placeholder_url("null") is True
    assert is_placeholder_url("not-a-url") is True
    assert is_placeholder_url("https://jobs.acmecorp.dev/opening/probe") is False


def test_probe_url_placeholder():
    assert probe_url("") == "bad"
    assert probe_url("TBD") == "bad"
    assert probe_url("not-a-url") == "bad"


def test_probe_url_fixture_hosts_short_circuit_without_http():
    """Fixture hosts must be bad locally — example.com can return HTTP 200."""
    assert probe_url("https://example.com/jobs/123") == "bad"
    assert probe_url("https://example.net/jobs/abc") == "bad"
    assert probe_url("https://test.com/jobs/1") == "bad"
    assert probe_url("http://localhost:3000/jobs/1") == "bad"
    assert probe_url("http://127.0.0.1/jobs/1") == "bad"


def test_probe_url_good(respx_mock):
    respx_mock.head("https://jobs.acmecorp.dev/opening/probe").mock(return_value=httpx.Response(200))
    assert probe_url("https://jobs.acmecorp.dev/opening/probe") == "good"


def test_probe_url_redirect(respx_mock):
    respx_mock.head("https://jobs.acmecorp.dev/opening/probe").mock(return_value=httpx.Response(302))
    assert probe_url("https://jobs.acmecorp.dev/opening/probe") == "good"


def test_probe_url_bad_404(respx_mock):
    respx_mock.head("https://jobs.acmecorp.dev/opening/probe").mock(return_value=httpx.Response(404))
    assert probe_url("https://jobs.acmecorp.dev/opening/probe") == "bad"


def test_probe_url_bad_500(respx_mock):
    respx_mock.head("https://jobs.acmecorp.dev/opening/probe").mock(return_value=httpx.Response(500))
    # 5xx is now treated as transient error, not permanent bad
    assert probe_url("https://jobs.acmecorp.dev/opening/probe") == "error"


def test_probe_url_timeout(respx_mock):
    respx_mock.head("https://jobs.acmecorp.dev/opening/probe").mock(side_effect=httpx.TimeoutException("timeout"))
    assert probe_url("https://jobs.acmecorp.dev/opening/probe") == "error"


def test_probe_url_network_error(respx_mock):
    respx_mock.head("https://jobs.acmecorp.dev/opening/probe").mock(side_effect=httpx.ConnectError("connection failed"))
    assert probe_url("https://jobs.acmecorp.dev/opening/probe") == "error"


def test_notify_with_probe_disabled(tmp_path, monkeypatch):
    """With probe disabled, main quality gates still apply; matching good URL notifies."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    db = Database(tmp_path / "db.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    job = JobRecord(
        company="Stripe",
        title="Engineer",
        url="https://stripe.com/jobs/123",
        sources=["test"],
    )
    assert notifier.notify(job) is True
    assert notifier.notify(job) is False


def test_notify_with_probe_enabled_good_url(tmp_path, respx_mock, monkeypatch):
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    respx_mock.head("https://stripe.com/jobs/good").mock(return_value=httpx.Response(200))
    # notify.probe_url may fall through to GET
    respx_mock.get("https://stripe.com/jobs/good").mock(return_value=httpx.Response(200))
    db = Database(tmp_path / "db.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    job = JobRecord(
        company="Stripe",
        title="Engineer",
        url="https://stripe.com/jobs/good",
        sources=["test"],
    )
    assert notifier.notify(job) is True


def test_notify_with_probe_enabled_bad_url(tmp_path, monkeypatch):
    """example.com / domain mismatch is blocked by main job_notify_block_reason (returns False)."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    db = Database(tmp_path / "db.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    job = JobRecord(
        company="TestCo",
        title="Engineer",
        url="https://example.com/bad",
        sources=["test"],
    )
    with patch("jobradar.notify.send_discord") as mock_discord:
        with patch("jobradar.notify.send_ntfy") as mock_ntfy:
            with patch("jobradar.notify.send_telegram") as mock_telegram:
                assert notifier.notify(job) is False
                mock_discord.assert_not_called()
                mock_ntfy.assert_not_called()
                mock_telegram.assert_not_called()


def test_notify_with_probe_enabled_placeholder_url(tmp_path, monkeypatch):
    """Placeholder URLs are blocked (no Discord/ntfy/Telegram)."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    db = Database(tmp_path / "db.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    job = JobRecord(
        company="TestCo",
        title="Engineer",
        url="TBD",
        sources=["test"],
    )
    with patch("jobradar.notify.send_discord") as mock_discord:
        with patch("jobradar.notify.send_ntfy") as mock_ntfy:
            with patch("jobradar.notify.send_telegram") as mock_telegram:
                assert notifier.notify(job) is False
                mock_discord.assert_not_called()
                mock_ntfy.assert_not_called()
                mock_telegram.assert_not_called()


def test_verify_links_cli_with_urls(tmp_path, respx_mock, capsys):
    from jobradar.cli import cmd_verify_links
    import argparse
    
    respx_mock.head("https://jobs.acmecorp.dev/good").mock(return_value=httpx.Response(200))
    respx_mock.head("https://jobs.acmecorp.dev/bad").mock(return_value=httpx.Response(404))
    
    args = argparse.Namespace(
        urls=["https://jobs.acmecorp.dev/good", "https://jobs.acmecorp.dev/bad"],
        priority_only=False,
        limit=None,
        mark_bad=False,
        verbose=True,
    )
    
    result = cmd_verify_links(args)
    assert result == 0
    
    captured = capsys.readouterr()
    assert "checked=2" in captured.out
    assert "good=1" in captured.out
    assert "bad=1" in captured.out


def test_verify_links_cli_from_db(tmp_path, respx_mock, capsys, monkeypatch):
    from jobradar.cli import cmd_verify_links
    import argparse
    
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "test.db"))
    
    db = Database(tmp_path / "test.db")
    
    job1 = JobRecord(
        company="CompanyA",
        title="Engineer A",
        url="https://jobs.acmecorp.dev/opening/probe1",
        sources=["test"],
    )
    job2 = JobRecord(
        company="CompanyB",
        title="Engineer B",
        url="https://jobs.acmecorp.dev/opening/probe2",
        sources=["test"],
    )
    
    db.upsert_job(job1)
    db.upsert_job(job2)
    
    respx_mock.head("https://jobs.acmecorp.dev/opening/probe1").mock(return_value=httpx.Response(200))
    respx_mock.head("https://jobs.acmecorp.dev/opening/probe2").mock(return_value=httpx.Response(404))
    
    args = argparse.Namespace(
        urls=None,
        priority_only=False,
        limit=None,
        mark_bad=True,
        verbose=False,
    )
    
    result = cmd_verify_links(args)
    assert result == 0
    
    captured = capsys.readouterr()
    assert "checked=2" in captured.out
    assert "good=1" in captured.out
    assert "bad=1" in captured.out
    assert "marked 1 jobs as closed" in captured.out
    
    job2_updated = db.get_job(job2.canonical_key)
    assert job2_updated is not None
    assert job2_updated.is_closed is True
