"""Tests for health CLI runtime gate reporting (overnight #17)."""

import argparse
import os
import re

import pytest

from jobradar.cli import cmd_health


def test_health_reports_runtime_gates(capsys, monkeypatch, tmp_path):
    """Health CLI reports notify window, link probe, alerts, max alerts."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JOBRADAR_NOTIFY_WINDOW_DAYS", "7")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "20")
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    # Check runtime gates section exists
    assert "Runtime gates:" in output
    
    # Check specific gates are reported
    assert "notify window: 7 days" in output
    assert "link probe: enabled" in output
    assert "alerts: enabled" in output
    assert "max alerts/scan: 20" in output


def test_health_reports_disabled_gates(capsys, monkeypatch, tmp_path):
    """Health CLI reports disabled states correctly."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "0")
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "0")
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "link probe: disabled" in output
    assert "alerts: paused" in output
    assert "max alerts/scan: unlimited" in output


def test_health_no_secret_values(capsys, monkeypatch, tmp_path):
    """
    CRITICAL: Health CLI must NEVER print secret values.
    
    Only non-secret runtime gate flags/settings are OK to print:
    - notify window days (public setting)
    - link probe enabled/disabled (public flag)
    - alerts enabled/paused (public flag)
    - max alerts per scan (public limit)
    - whether Director/Discord/ntfy/etc are "configured" (yes/no only)
    
    NEVER print:
    - Webhook URLs
    - API tokens
    - Bot tokens
    - Database credentials
    - File paths with user info
    """
    # Simulate leaked secrets in env
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/12345/SECRET_TOKEN")
    monkeypatch.setenv("NTFY_TOKEN", "tk_secret_abc123")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
    monkeypatch.setenv("GROK_BOT_WEBHOOK_JOB_ANALYST", "https://api.grok.com/webhooks/SECRET")
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    # Ensure NO secret values appear in output
    assert "SECRET_TOKEN" not in output
    assert "tk_secret_abc123" not in output
    assert "ABCdefGHIjklMNOpqrsTUVwxyz" not in output
    assert "api.grok.com" not in output
    assert "webhooks/SECRET" not in output
    
    # Only "configured" or "skipped" labels should appear
    assert "discord: configured" in output or "notifiers:" in output
    
    # Should NOT contain full webhook URLs
    assert "https://discord.com/api/webhooks/" not in output
    assert "https://api.grok.com/" not in output


def test_health_default_values(capsys, monkeypatch, tmp_path):
    """Health CLI uses correct defaults when env vars not set."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "test.db"))
    
    # Clear all gate env vars to test defaults
    for key in [
        "JOBRADAR_NOTIFY_WINDOW_DAYS",
        "JOBRADAR_LINK_PROBE",
        "JOBRADAR_ALERTS_ENABLED",
        "JOBRADAR_MAX_ALERTS_PER_SCAN",
    ]:
        monkeypatch.delenv(key, raising=False)
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    # Check defaults (from notify.py constants)
    assert "notify window: 3 days" in output  # NOTIFY_WINDOW_DAYS = 3
    assert "link probe: enabled" in output    # default: 1
    assert "alerts: enabled" in output         # default: 1
    assert "max alerts/scan: unlimited" in output  # default: 0 (unlimited)


def test_health_require_posted_at_flag(capsys, monkeypatch, tmp_path):
    """Health CLI reports require_posted_at setting."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "require posted_at: yes" in output


def test_health_require_posted_at_disabled(capsys, monkeypatch, tmp_path):
    """Health CLI reports require_posted_at disabled."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "0")
    
    args = argparse.Namespace()
    result = cmd_health(args)
    
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "require posted_at: no" in output


def test_health_director_configured_status(capsys, monkeypatch, tmp_path):
    """Health CLI reports Director configured status (overnight #17 requirement)."""
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "test.db"))
    
    # No Director keys set
    args = argparse.Namespace()
    result = cmd_health(args)
    assert result == 0
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "director:" in output
    # Should be "skipped" or "configured" (not secret URL)
    assert "skipped until keys set" in output or "configured" in output
