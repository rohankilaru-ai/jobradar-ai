"""Pytest configuration and fixtures."""

import os
import pytest


@pytest.fixture(autouse=True)
def disable_link_probe_in_tests(monkeypatch):
    """Disable live HTTP probing in tests by default."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")


@pytest.fixture(autouse=True)
def disable_live_notifications_in_tests(monkeypatch):
    """
    Clear all notification env vars to prevent live sends during tests.
    
    This is a safety fixture that ensures tests NEVER send to live Discord/ntfy/Telegram,
    even if .env or environment has these vars set.
    """
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("NTFY_SERVER", raising=False)
    monkeypatch.delenv("NTFY_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
