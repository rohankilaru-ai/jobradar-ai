"""Pytest configuration and fixtures."""

import os
import pytest


@pytest.fixture(autouse=True)
def disable_link_probe_in_tests(monkeypatch):
    """Disable live HTTP probing in tests by default."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    # Prevent cli.main() → _load_env() from re-applying local .env over test delenv.
    monkeypatch.setenv("JOBRADAR_SKIP_DOTENV", "1")


@pytest.fixture(autouse=True)
def allow_first_seen_fallback_in_tests(monkeypatch):
    """Tests historically use first_seen_at without posted_at; keep that unless a test opts in."""
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "0")
    # Use code default (14-day) unless a test explicitly overrides. Prevents a
    # stale process env / accidental dotenv leak from shrinking the window.
    monkeypatch.delenv("JOBRADAR_NOTIFY_WINDOW_DAYS", raising=False)


@pytest.fixture(autouse=True)
def disable_live_notifications_in_tests(monkeypatch):
    """
    Clear all notification env vars to prevent live sends during tests.
    
    This is a safety fixture that ensures tests NEVER send to live Discord/ntfy/Telegram,
    even if .env or environment has these vars set.
    """
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_PRIORITY", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_FORTUNE500", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_F500", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_OTHER", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("NTFY_SERVER", raising=False)
    monkeypatch.delenv("NTFY_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
