"""Tests for unified probe logic (overnight #17).

Verifies that verify-links CLI and notify gates share one probe definition.
"""

import httpx
import pytest

from jobradar.link_probe import probe_url, probe_url_for_notify


def test_probe_url_good_maps_to_true(respx_mock):
    """probe_url 'good' (2xx) → probe_url_for_notify True"""
    respx_mock.head("https://example.com/job").mock(return_value=httpx.Response(200))
    
    assert probe_url("https://example.com/job") == "good"
    assert probe_url_for_notify("https://example.com/job") is True


def test_probe_url_redirect_maps_to_true(respx_mock):
    """probe_url 'good' (3xx) → probe_url_for_notify True"""
    respx_mock.head("https://example.com/job").mock(return_value=httpx.Response(302))
    
    assert probe_url("https://example.com/job") == "good"
    assert probe_url_for_notify("https://example.com/job") is True


def test_probe_url_bad_404_maps_to_false(respx_mock):
    """probe_url 'bad' (404) → probe_url_for_notify False"""
    respx_mock.head("https://example.com/job").mock(return_value=httpx.Response(404))
    
    assert probe_url("https://example.com/job") == "bad"
    assert probe_url_for_notify("https://example.com/job") is False


def test_probe_url_bad_500_maps_to_false(respx_mock):
    """probe_url 'error' (5xx transient) → probe_url_for_notify False
    
    PR #38: 5xx now treated as 'error' (transient) instead of 'bad' (permanent).
    This allows jobs to be retried later instead of being permanently silenced.
    """
    respx_mock.head("https://example.com/job").mock(return_value=httpx.Response(500))
    
    assert probe_url("https://example.com/job") == "error"
    assert probe_url_for_notify("https://example.com/job") is False


def test_probe_url_error_timeout_maps_to_false(respx_mock):
    """probe_url 'error' (timeout) → probe_url_for_notify False"""
    respx_mock.head("https://example.com/job").mock(side_effect=httpx.TimeoutException("timeout"))
    
    assert probe_url("https://example.com/job") == "error"
    assert probe_url_for_notify("https://example.com/job") is False


def test_probe_url_error_network_maps_to_false(respx_mock):
    """probe_url 'error' (network) → probe_url_for_notify False"""
    respx_mock.head("https://example.com/job").mock(side_effect=httpx.ConnectError("connection failed"))
    
    assert probe_url("https://example.com/job") == "error"
    assert probe_url_for_notify("https://example.com/job") is False


def test_probe_url_403_job_url_accepts(respx_mock):
    """
    Notify-specific: 403 on job-shaped URL → probe_url_for_notify True.
    
    This preserves existing notify behavior where 403 is acceptable for
    URLs containing job/career/position keywords (common ATS pattern).
    """
    url = "https://example.com/careers/job/12345"
    respx_mock.head(url).mock(return_value=httpx.Response(403))
    
    assert probe_url(url) == "bad"
    assert probe_url_for_notify(url) is True


def test_probe_url_403_non_job_url_rejects(respx_mock):
    """403 on non-job URL → probe_url_for_notify False"""
    url = "https://example.com/random/page"
    respx_mock.head(url).mock(return_value=httpx.Response(403))
    
    assert probe_url(url) == "bad"
    assert probe_url_for_notify(url) is False


def test_probe_url_placeholder_empty():
    """Empty/placeholder URLs → 'bad' → False"""
    assert probe_url("") == "bad"
    assert probe_url_for_notify("") is False


def test_probe_url_placeholder_tbd():
    """TBD placeholder → 'bad' → False"""
    assert probe_url("TBD") == "bad"
    assert probe_url_for_notify("TBD") is False


def test_probe_url_placeholder_invalid_scheme():
    """Invalid scheme → 'bad' → False"""
    assert probe_url("not-a-url") == "bad"
    assert probe_url_for_notify("not-a-url") is False


def test_notify_uses_unified_probe(tmp_path, respx_mock, monkeypatch):
    """
    End-to-end: notify.probe_url delegates to link_probe.probe_url_for_notify.
    
    This ensures verify-links and notify gates share one probe definition.
    """
    from jobradar.db import Database
    from jobradar.models import JobRecord
    from jobradar.notify import Notifier
    
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    # Mock a good URL
    url = "https://stripe.com/jobs/123"
    respx_mock.head(url).mock(return_value=httpx.Response(200))
    respx_mock.get(url).mock(return_value=httpx.Response(200))
    
    db = Database(tmp_path / "db.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="Stripe",
        title="Engineer",
        url=url,
        sources=["test"],
    )
    
    # Should alert (probe passes)
    assert notifier.notify(job) is True


def test_notify_rejects_bad_probe(tmp_path, respx_mock, monkeypatch):
    """notify rejects 404 via unified probe"""
    from jobradar.db import Database
    from jobradar.models import JobRecord
    from jobradar.notify import Notifier
    
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    url = "https://badco.com/job/404"
    respx_mock.head(url).mock(return_value=httpx.Response(404))
    
    db = Database(tmp_path / "db.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="BadCo",
        title="Engineer",
        url=url,
        sources=["test"],
    )
    
    # Should not alert (probe fails)
    assert notifier.notify(job) is False
