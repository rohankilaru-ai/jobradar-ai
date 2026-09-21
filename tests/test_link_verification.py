"""Tests for link verification and URL quality gates."""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import (
    Notifier,
    job_notify_block_reason,
    probe_url,
    sanitize_job_url,
    strip_html,
)


def test_sanitize_job_url():
    """Verify trailing junk is stripped from URLs."""
    assert sanitize_job_url('https://example.com/job"') == "https://example.com/job"
    assert sanitize_job_url("https://example.com/job'") == "https://example.com/job"
    assert sanitize_job_url("https://example.com/job>") == "https://example.com/job"
    assert sanitize_job_url("https://example.com/job)") == "https://example.com/job"
    assert sanitize_job_url("https://example.com/job`") == "https://example.com/job"
    assert sanitize_job_url("https://example.com/job\\") == "https://example.com/job"
    assert sanitize_job_url("https://example.com/job,") == "https://example.com/job"
    assert sanitize_job_url("https://example.com/job;") == "https://example.com/job"
    assert sanitize_job_url("https://example.com/job]") == "https://example.com/job"
    assert sanitize_job_url("https://example.com/job  ") == "https://example.com/job"
    # Real-world example from Jane Street
    assert sanitize_job_url('https://janestreet.com/join-jane-street/position/7527629002/"') == \
           "https://janestreet.com/join-jane-street/position/7527629002/"


def test_strip_html():
    """Verify HTML tags are removed."""
    assert strip_html("<b>Company</b>") == "Company"
    assert strip_html("Company <span>Inc</span>") == "Company Inc"
    assert strip_html("<a href='url'>Link</a>") == "Link"
    assert strip_html("Regular Company Name") == "Regular Company Name"
    assert strip_html("Company & Associates") == "Company & Associates"
    assert strip_html("") == ""


def test_probe_url_with_mocked_responses(monkeypatch):
    """Verify URL probing logic with mocked HTTP responses."""
    # Enable link probe for this test
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    # Mock successful HEAD (2xx)
    with patch("httpx.head") as mock_head:
        mock_head.return_value = Mock(status_code=200)
        assert probe_url("https://valid-site.com/job") is True
    
    # Mock 404 (should fail)
    with patch("httpx.head") as mock_head, patch("httpx.get") as mock_get:
        mock_head.return_value = Mock(status_code=404)
        mock_get.return_value = Mock(status_code=404)
        assert probe_url("https://dead-link.com/job") is False
    
    # Mock 403 with job-shaped URL (should pass)
    with patch("httpx.head") as mock_head:
        mock_head.return_value = Mock(status_code=403)
        assert probe_url("https://greenhouse.io/careers/position/123") is True
    
    # Mock 403 with non-job URL (should fail)
    with patch("httpx.head") as mock_head, patch("httpx.get") as mock_get:
        mock_head.return_value = Mock(status_code=403)
        mock_get.return_value = Mock(status_code=403)
        assert probe_url("https://random-site.com/page") is False
    
    # Mock HEAD 405, GET 200 (some servers don't support HEAD)
    with patch("httpx.head") as mock_head, patch("httpx.get") as mock_get:
        mock_head.return_value = Mock(status_code=405)
        mock_get.return_value = Mock(status_code=200)
        assert probe_url("https://another-site.com/job") is True
    
    # Mock exception (should fail gracefully)
    with patch("httpx.head") as mock_head:
        mock_head.side_effect = Exception("Connection timeout")
        assert probe_url("https://timeout.com/job") is False


def test_job_notify_block_reason_html_tags():
    """Verify jobs with HTML tags are blocked."""
    job_html_company = JobRecord(
        company="<b>TechCorp</b>",
        title="Software Engineer Intern",
        url="https://realsite.com/jobs/123",
    )
    reason = job_notify_block_reason(job_html_company)
    assert reason is not None
    assert "HTML in company" in reason
    
    job_html_title = JobRecord(
        company="CleanCorp",
        title="<span>SWE Intern</span>",
        url="https://realsite.com/jobs/456",
    )
    reason = job_notify_block_reason(job_html_title)
    assert reason is not None
    assert "HTML in title" in reason


def test_job_notify_block_reason_empty_url():
    """Verify jobs with empty URLs are blocked."""
    job = JobRecord(
        company="NoURL Corp",
        title="Software Engineer Intern",
        url="",
    )
    reason = job_notify_block_reason(job)
    assert reason is not None
    assert "empty URL" in reason


def test_job_notify_block_reason_example_urls():
    """Verify test fixture URLs (example.com/org) are blocked."""
    job_example_com = JobRecord(
        company="Example Corp",
        title="SWE Intern",
        url="https://example.com/job123",
    )
    reason = job_notify_block_reason(job_example_com)
    assert reason is not None
    assert "example.com" in reason or "test fixture" in reason
    
    job_example_org = JobRecord(
        company="Example Org",
        title="ML Intern",
        url="https://example.org/position",
    )
    reason = job_notify_block_reason(job_example_org)
    assert reason is not None
    assert "example.org" in reason or "test fixture" in reason


def test_job_notify_block_reason_probe_failure(monkeypatch):
    """Verify jobs with hard URL probe failures (404) are blocked."""
    # Enable link probe for this test
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    with patch("jobradar.notify.detailed_probe_url") as mock_probe:
        # Return "bad" for hard failure (404, etc.)
        mock_probe.return_value = "bad"
        
        job = JobRecord(
            company="DeadSite",
            title="Software Engineer Intern",
            url="https://deadsite.com/job123",
        )
        reason = job_notify_block_reason(job)
        assert reason is not None
        assert "probe failed" in reason


def test_job_notify_block_reason_valid_job(monkeypatch):
    """Verify valid jobs pass all checks."""
    # Enable link probe for this test
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    
    with patch("jobradar.notify.probe_url") as mock_probe:
        mock_probe.return_value = True
        
        job = JobRecord(
            company="Valid Corp",
            title="ML Engineer Intern",
            url="https://valid-site.com/careers/position/12345",
        )
        reason = job_notify_block_reason(job)
        assert reason is None


def test_notifier_skips_jobs_with_block_reasons(tmp_path):
    """Verify Notifier.notify respects job_notify_block_reason."""
    db = Database(tmp_path / "notify.db")
    notifier = Notifier(path=tmp_path / "notifications.jsonl", db=db)
    
    # Job with HTML in company should not notify
    with patch("jobradar.notify.probe_url") as mock_probe:
        mock_probe.return_value = True
        
        job_html = JobRecord(
            company="<div>BadCorp</div>",
            title="SWE Intern",
            url="https://realsite.com/jobs/1",
        )
        assert notifier.notify(job_html) is False
    
    # Job with valid data should notify
    with patch("jobradar.notify.probe_url") as mock_probe:
        mock_probe.return_value = True
        
        job_valid = JobRecord(
            company="GoodCorp",
            title="ML Intern",
            url="https://goodcorp.com/careers/intern",
        )
        assert notifier.notify(job_valid) is True
    
    # Verify only valid job was notified
    notifications_file = Path(tmp_path / "notifications.jsonl")
    if notifications_file.exists():
        notifications = notifications_file.read_text().strip().split("\n")
        assert len(notifications) == 1
        data = json.loads(notifications[0])
        assert data["job"]["company"] == "GoodCorp"


def test_link_probe_disabled_in_tests(monkeypatch):
    """Verify JOBRADAR_LINK_PROBE=0 disables probing (set by conftest.py)."""
    from jobradar.notify import link_probe_enabled
    
    # conftest.py should have set this to 0
    assert os.environ.get("JOBRADAR_LINK_PROBE") == "0"
    assert link_probe_enabled() is False
    
    # When disabled, probe_url should always return True
    assert probe_url("https://any-url.com/job") is True
    assert probe_url("https://404-url.com/missing") is True


def test_verify_links_cli_exists():
    """Verify verify-links CLI command is registered."""
    from jobradar.cli import build_parser
    
    parser = build_parser()
    help_text = parser.format_help()
    assert "verify-links" in help_text
    
    args = parser.parse_args(["verify-links"])
    assert args.priority_only is False
    assert args.limit is None
    
    args_limit = parser.parse_args(["verify-links", "--limit", "10"])
    assert args_limit.limit == 10
