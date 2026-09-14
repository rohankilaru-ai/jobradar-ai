"""Regression test: pytest must NEVER call live Discord/ntfy/Telegram webhooks."""

from unittest.mock import MagicMock, patch

import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import Notifier, send_discord, send_ntfy, send_telegram


def test_send_discord_blocked_when_pytest_current_test_set(monkeypatch):
    """
    REGRESSION TEST for production bug: send_discord must refuse to send when PYTEST_CURRENT_TEST is set.
    
    This ensures that even if DISCORD_WEBHOOK_URL leaks into the test environment (e.g., from .env),
    the send_discord function will refuse to make live HTTP calls.
    """
    # Simulate .env setting DISCORD_WEBHOOK_URL
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/fake/webhook")
    
    # Pytest automatically sets PYTEST_CURRENT_TEST when running tests
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_no_live_notify_in_tests.py::test_send_discord_blocked")
    
    # Call send_discord - should return "skipped" without making any HTTP call
    result = send_discord("Test notification")
    assert result == "skipped"


def test_send_ntfy_blocked_when_pytest_current_test_set(monkeypatch):
    """Ensure send_ntfy refuses to send during pytest."""
    monkeypatch.setenv("NTFY_TOPIC", "fake-topic")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_no_live_notify_in_tests.py::test_send_ntfy_blocked")
    
    result = send_ntfy("Test notification")
    assert result == "skipped"


def test_send_telegram_blocked_when_pytest_current_test_set(monkeypatch):
    """Ensure send_telegram refuses to send during pytest."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake-chat-id")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_no_live_notify_in_tests.py::test_send_telegram_blocked")
    
    result = send_telegram("Test notification")
    assert result == "skipped"


def test_notifier_no_httpx_post_even_with_webhook_url_set(tmp_path, monkeypatch):
    """
    CRITICAL REGRESSION TEST: Notifier.notify must NEVER call httpx.post during pytest.
    
    This test simulates the exact production bug scenario:
    - User has DISCORD_WEBHOOK_URL in .env
    - User runs pytest
    - Test creates JobRecord with fixture data (Stripe, GoodCorp, etc.)
    - Notifier.notify is called
    
    Expected: NO httpx.post calls to Discord/ntfy/Telegram webhooks
    """
    # Simulate leaked env vars from .env
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/12345/fake")
    monkeypatch.setenv("NTFY_TOPIC", "jobradar-alerts")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654321")
    
    # Pytest sets this automatically
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_no_live_notify_in_tests.py::test_notifier_no_httpx_post")
    
    # Disable link probe (already done by conftest, but be explicit)
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    # Create test job with a URL that passes quality gate (4+ digit ID)
    # This ensures we test the PYTEST_CURRENT_TEST guard, not just URL quality blocking
    job = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://stripe.com/jobs/1234567",  # Long enough to pass URL quality gate
        sources=["test"],
        priority=True,
    )
    
    # Mock httpx.post to track calls and fail if called
    with patch("jobradar.notify.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        
        # This should write JSONL but NOT call httpx.post
        result = notifier.notify(job, silent=False)
        
        # Verify no HTTP calls were made
        mock_post.assert_not_called()
    
    # Verify JSONL was still written
    assert (tmp_path / "notify.jsonl").exists()
    content = (tmp_path / "notify.jsonl").read_text()
    assert "Stripe" in content


def test_conftest_fixture_clears_notification_env_vars(monkeypatch):
    """
    Verify that conftest.py autouse fixture clears notification env vars.
    
    This is belt-and-suspenders: even if user has DISCORD_WEBHOOK_URL in .env,
    conftest should clear it before tests run.
    """
    # Note: conftest.py's disable_live_notifications_in_tests fixture should have
    # already cleared these, but let's verify the fixture exists and works
    import os
    
    # These should all be cleared by conftest autouse fixture
    assert os.environ.get("DISCORD_WEBHOOK_URL") is None
    assert os.environ.get("NTFY_TOPIC") is None
    assert os.environ.get("TELEGRAM_BOT_TOKEN") is None
    assert os.environ.get("TELEGRAM_CHAT_ID") is None


def test_multiple_test_jobs_no_live_sends(tmp_path, monkeypatch):
    """
    Test the exact scenario from the bug report: multiple fixture jobs with realistic data.
    
    Bug scenario from screenshot:
    - Stripe SWE Intern (https://stripe.com/jobs/1)
    - Stripe careers (https://stripe.com/careers/intern)
    - GoodCorp
    - Google (careers.google.com/jobs/results/123456)
    
    All these should be written to JSONL but NEVER sent to live Discord.
    """
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/fake/url")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_no_live_notify_in_tests.py::test_multiple_test_jobs")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    test_jobs = [
        JobRecord(
            company="Stripe",
            title="Software Engineer Intern",
            location="SF",
            url="https://stripe.com/jobs/1",
            sources=["test"],
        ),
        JobRecord(
            company="Stripe",
            title="SWE Intern",
            location="SF",
            url="https://stripe.com/careers/intern",
            sources=["test"],
        ),
        JobRecord(
            company="GoodCorp",
            title="ML Intern",
            location="NYC",
            url="https://goodcorp.com/careers/ml",
            sources=["test"],
        ),
        JobRecord(
            company="Google",
            title="Software Engineer Intern",
            location="Mountain View",
            url="https://careers.google.com/jobs/results/123456",
            sources=["test"],
        ),
    ]
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        for job in test_jobs:
            notifier.notify(job, silent=False)
        
        # Critical: NO httpx.post calls should have been made
        mock_post.assert_not_called()
    
    # Verify JSONL has all jobs
    content = (tmp_path / "notify.jsonl").read_text()
    assert "Stripe" in content
    assert "GoodCorp" in content
    assert "Google" in content
