"""Tests for Discord/ntfy/Telegram handling when webhooks/tokens are missing or empty.

Ensures that empty/missing credentials skip silently without blocking the pipeline.
"""

from unittest.mock import MagicMock, patch

import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import (
    Notifier,
    discord_configured,
    get_discord_webhook_url,
    ntfy_configured,
    send_discord,
    send_ntfy,
    send_telegram,
    telegram_configured,
)


# --- Tests for empty webhook detection ---


def test_discord_configured_with_empty_string(monkeypatch):
    """Discord should not be considered configured when env var is empty string."""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "  ")  # whitespace only
    assert discord_configured() is False


def test_discord_configured_with_whitespace(monkeypatch):
    """Discord should not be considered configured when env var is whitespace."""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "   \t\n   ")
    assert discord_configured() is False


def test_ntfy_configured_with_empty_string(monkeypatch):
    """ntfy should not be considered configured when NTFY_TOPIC is empty."""
    monkeypatch.setenv("NTFY_TOPIC", "")
    assert ntfy_configured() is False


def test_ntfy_configured_with_whitespace(monkeypatch):
    """ntfy should not be considered configured when NTFY_TOPIC is whitespace."""
    monkeypatch.setenv("NTFY_TOPIC", "   \t\n   ")
    assert ntfy_configured() is False


def test_telegram_configured_with_empty_token(monkeypatch):
    """Telegram should not be configured when token is empty."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    assert telegram_configured() is False


def test_telegram_configured_with_empty_chat_id(monkeypatch):
    """Telegram should not be configured when chat_id is empty."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "valid-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    assert telegram_configured() is False


def test_telegram_configured_with_whitespace(monkeypatch):
    """Telegram should not be configured when values are whitespace."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "  \t  ")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "   \n   ")
    assert telegram_configured() is False


# --- Tests for send_* functions with empty credentials ---


def test_send_discord_skips_when_no_webhook_url(monkeypatch):
    """send_discord should return 'skipped' when webhook URL is not configured."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    # Clear all Discord webhook env vars
    for key in ["DISCORD_WEBHOOK_URL", "DISCORD_WEBHOOK_PRIORITY",
                "DISCORD_WEBHOOK_FORTUNE500", "DISCORD_WEBHOOK_F500",
                "DISCORD_WEBHOOK_OTHER"]:
        monkeypatch.delenv(key, raising=False)
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = send_discord("Test message", tier="priority")
        assert result == "skipped"
        mock_post.assert_not_called()


def test_send_discord_skips_when_webhook_url_is_empty(monkeypatch):
    """send_discord should return 'skipped' when webhook URL is empty string."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "  ")  # whitespace
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = send_discord("Test message", tier="priority")
        assert result == "skipped"
        mock_post.assert_not_called()


def test_send_ntfy_skips_when_topic_is_empty(monkeypatch):
    """send_ntfy should return 'skipped' when NTFY_TOPIC is empty."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("NTFY_TOPIC", "")
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = send_ntfy("Test message")
        assert result == "skipped"
        mock_post.assert_not_called()


def test_send_ntfy_skips_when_topic_is_whitespace(monkeypatch):
    """send_ntfy should return 'skipped' when NTFY_TOPIC is whitespace."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("NTFY_TOPIC", "   \t\n   ")
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = send_ntfy("Test message")
        assert result == "skipped"
        mock_post.assert_not_called()


def test_send_telegram_skips_when_token_is_empty(monkeypatch):
    """send_telegram should return 'skipped' when bot token is empty."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = send_telegram("Test message")
        assert result == "skipped"
        mock_post.assert_not_called()


def test_send_telegram_skips_when_chat_id_is_empty(monkeypatch):
    """send_telegram should return 'skipped' when chat_id is empty."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "valid-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = send_telegram("Test message")
        assert result == "skipped"
        mock_post.assert_not_called()


def test_send_telegram_skips_when_both_are_whitespace(monkeypatch):
    """send_telegram should return 'skipped' when both token and chat_id are whitespace."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "  \t  ")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "   \n   ")
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = send_telegram("Test message")
        assert result == "skipped"
        mock_post.assert_not_called()


# --- Tests for get_discord_webhook_url with empty values ---


def test_get_discord_webhook_url_empty_tier_specific(monkeypatch):
    """get_discord_webhook_url should return empty when tier URL is empty."""
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "")
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    
    url = get_discord_webhook_url("priority")
    assert url == ""


def test_get_discord_webhook_url_whitespace_tier_specific(monkeypatch):
    """get_discord_webhook_url should return empty when tier URL is whitespace."""
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "   \t   ")
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    
    url = get_discord_webhook_url("priority")
    assert url == ""


def test_get_discord_webhook_url_empty_fallback(monkeypatch):
    """get_discord_webhook_url should return empty when fallback URL is empty."""
    monkeypatch.delenv("DISCORD_WEBHOOK_PRIORITY", raising=False)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    
    url = get_discord_webhook_url("priority")
    assert url == ""


# --- Integration tests: Notifier with empty credentials ---


def test_notifier_handles_empty_discord_webhook_gracefully(tmp_path, monkeypatch):
    """Notifier.notify should succeed even when Discord webhook is empty."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "  ")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://stripe.com/careers/positions/software-engineer-intern-123456",
        sources=["test"],
        priority=True,
    )
    
    # Should not raise; Discord is skipped
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        assert result is True
        mock_post.assert_not_called()
    
    # JSONL should still be written
    assert (tmp_path / "notify.jsonl").exists()


def test_notifier_handles_empty_ntfy_topic_gracefully(tmp_path, monkeypatch):
    """Notifier.notify should succeed even when NTFY_TOPIC is empty."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("NTFY_TOPIC", "")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="Google",
        title="SWE Intern",
        location="Mountain View, CA",
        url="https://careers.google.com/jobs/results/123456789012345678901",
        sources=["test"],
    )
    
    # Should not raise; ntfy is skipped
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        assert result is True
        mock_post.assert_not_called()
    
    # JSONL should still be written
    assert (tmp_path / "notify.jsonl").exists()


def test_notifier_handles_empty_telegram_credentials_gracefully(tmp_path, monkeypatch):
    """Notifier.notify should succeed even when Telegram credentials are empty."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="Meta",
        title="ML Research Intern",
        location="Menlo Park, CA",
        url="https://www.metacareers.com/jobs/123456789012345",
        sources=["test"],
    )
    
    # Should not raise; Telegram is skipped
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        assert result is True
        mock_post.assert_not_called()
    
    # JSONL should still be written
    assert (tmp_path / "notify.jsonl").exists()


def test_notifier_handles_all_empty_credentials_gracefully(tmp_path, monkeypatch):
    """Notifier.notify should succeed even when all notification credentials are empty."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    # Set all to empty
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "")
    monkeypatch.setenv("DISCORD_WEBHOOK_FORTUNE500", "")
    monkeypatch.setenv("DISCORD_WEBHOOK_OTHER", "")
    monkeypatch.setenv("NTFY_TOPIC", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="OpenAI",
        title="Research Engineer Intern",
        location="San Francisco, CA",
        url="https://openai.com/careers/research-engineer-intern-summer-2027",
        sources=["test"],
        priority=True,
    )
    
    # Should not raise; all channels are skipped
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = notifier.notify(job, silent=False)
        assert result is True
        mock_post.assert_not_called()
    
    # JSONL should still be written
    assert (tmp_path / "notify.jsonl").exists()
    content = (tmp_path / "notify.jsonl").read_text()
    assert "OpenAI" in content
    assert "Research Engineer Intern" in content


def test_notifier_no_warnings_when_credentials_empty(tmp_path, monkeypatch, caplog):
    """Notifier should not log warnings when credentials are empty (just skip silently)."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    monkeypatch.setenv("NTFY_TOPIC", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="Databricks",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://databricks.com/company/careers/open-positions/job?gh_jid=123456",
        sources=["test"],
    )
    
    with caplog.at_level("WARNING"):
        notifier.notify(job, silent=False)
    
    # No warnings should be logged for skipped channels
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    # Should not have "failed" in warnings (empty credentials are not failures)
    for msg in warning_messages:
        assert "failed" not in msg.lower()
