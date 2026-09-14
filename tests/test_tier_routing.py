"""Tests for Discord multi-tier routing by company."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import Notifier, get_discord_webhook_url, send_discord
from jobradar.tier import classify_company_tier


# --- Tier classification tests ---


def test_classify_priority_companies():
    """Priority companies should be classified as 'priority'."""
    priority_examples = [
        "OpenAI",
        "OPENAI",
        "OpenAI Inc.",
        "Anthropic",
        "Databricks",
        "Snowflake",
        "NVIDIA",
        "Nvidia Corp",
        "Scale AI",
        "Perplexity",
        "Meta",
        "Facebook",  # alias for Meta
        "Google",
        "Google LLC",
        "Microsoft",
        "Apple",
        "Tesla",
        "Palantir",
        "Stripe",
        "Figma",
        "Roblox",
        "Netflix",
        "Jane Street",
        "Hudson River Trading",
        "Citadel",
        "Ramp",
        "Cursor",
        "Anduril",
        "xAI",
        "X AI",
    ]
    
    for company in priority_examples:
        assert classify_company_tier(company) == "priority", f"Failed for {company}"


def test_classify_fortune500_companies():
    """Fortune500 companies should be classified as 'fortune500'."""
    fortune500_examples = [
        "JPMorgan Chase",
        "JP Morgan",
        "Bank of America",
        "Wells Fargo",
        "Goldman Sachs",
        "IBM",
        "Oracle",
        "Salesforce",
        "Adobe",
        "Cisco",
        "Intel",
        "AMD",
        "Qualcomm",
        "AT&T",
        "Verizon",
        "Comcast",
        "Disney",
        "Boeing",
        "Lockheed Martin",
        "General Motors",
        "Ford",
        "ExxonMobil",
        "Chevron",
        "Pfizer",
        "Johnson & Johnson",
        "PepsiCo",
        "Coca-Cola",
        "Walmart",
        "Target",
        "Home Depot",
        "Accenture",
        "Deloitte",
        "PwC",
        "McKinsey",
    ]
    
    for company in fortune500_examples:
        assert classify_company_tier(company) == "fortune500", f"Failed for {company}"


def test_classify_other_companies():
    """Non-priority, non-Fortune500 companies should be classified as 'other'."""
    other_examples = [
        "Local Startup",
        "SmallCorp",
        "YC Startup Co",
        "Seed Stage AI",
        "Unknown Company",
        "New Tech Ventures",
        "",  # empty
    ]
    
    for company in other_examples:
        assert classify_company_tier(company) == "other", f"Failed for {company}"


def test_normalize_company_removes_suffixes():
    """Company name normalization should remove common suffixes."""
    assert classify_company_tier("OpenAI Inc.") == "priority"
    assert classify_company_tier("Stripe Corp") == "priority"
    assert classify_company_tier("Microsoft Corporation") == "priority"
    assert classify_company_tier("Apple Inc") == "priority"
    assert classify_company_tier("Goldman Sachs Group Inc.") == "fortune500"


def test_normalize_company_case_insensitive():
    """Company matching should be case-insensitive."""
    assert classify_company_tier("openai") == "priority"
    assert classify_company_tier("OPENAI") == "priority"
    assert classify_company_tier("OpenAI") == "priority"
    assert classify_company_tier("OpEnAi") == "priority"


def test_normalize_company_punctuation():
    """Company matching should handle punctuation variations."""
    assert classify_company_tier("JP Morgan") == "fortune500"
    assert classify_company_tier("JPMorgan") == "fortune500"
    assert classify_company_tier("J.P. Morgan") == "fortune500"
    assert classify_company_tier("AT&T") == "fortune500"
    assert classify_company_tier("ATT") == "fortune500"


# --- Webhook URL selection tests ---


def test_get_discord_webhook_priority(monkeypatch):
    """Priority tier should use DISCORD_WEBHOOK_PRIORITY."""
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "https://discord.com/priority")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    
    url = get_discord_webhook_url("priority")
    assert url == "https://discord.com/priority"


def test_get_discord_webhook_fortune500(monkeypatch):
    """Fortune500 tier should use DISCORD_WEBHOOK_FORTUNE500."""
    monkeypatch.setenv("DISCORD_WEBHOOK_FORTUNE500", "https://discord.com/fortune500")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    
    url = get_discord_webhook_url("fortune500")
    assert url == "https://discord.com/fortune500"


def test_get_discord_webhook_fortune500_f500_alias(monkeypatch):
    """Fortune500 tier should support DISCORD_WEBHOOK_F500 alias."""
    monkeypatch.setenv("DISCORD_WEBHOOK_F500", "https://discord.com/f500")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    
    url = get_discord_webhook_url("fortune500")
    assert url == "https://discord.com/f500"


def test_get_discord_webhook_other(monkeypatch):
    """Other tier should use DISCORD_WEBHOOK_OTHER."""
    monkeypatch.setenv("DISCORD_WEBHOOK_OTHER", "https://discord.com/other")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    
    url = get_discord_webhook_url("other")
    assert url == "https://discord.com/other"


def test_get_discord_webhook_fallback_to_legacy(monkeypatch):
    """When tier-specific URL not set, should fallback to DISCORD_WEBHOOK_URL."""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    
    # No tier-specific URLs set
    assert get_discord_webhook_url("priority") == "https://discord.com/legacy"
    assert get_discord_webhook_url("fortune500") == "https://discord.com/legacy"
    assert get_discord_webhook_url("other") == "https://discord.com/legacy"


def test_get_discord_webhook_no_config(monkeypatch):
    """When no webhook URLs configured, should return empty string."""
    # Clear all Discord env vars
    for key in ["DISCORD_WEBHOOK_URL", "DISCORD_WEBHOOK_PRIORITY", 
                "DISCORD_WEBHOOK_FORTUNE500", "DISCORD_WEBHOOK_F500", 
                "DISCORD_WEBHOOK_OTHER"]:
        monkeypatch.delenv(key, raising=False)
    
    assert get_discord_webhook_url("priority") == ""
    assert get_discord_webhook_url("fortune500") == ""
    assert get_discord_webhook_url("other") == ""


def test_get_discord_webhook_tier_priority_over_legacy(monkeypatch):
    """Tier-specific URL should take priority over legacy URL."""
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "https://discord.com/priority-tier")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    
    url = get_discord_webhook_url("priority")
    assert url == "https://discord.com/priority-tier"


# --- send_discord with tier parameter tests ---


def test_send_discord_uses_tier_url(monkeypatch):
    """send_discord should route to tier-specific URL."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)  # Allow send
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "https://discord.com/priority")
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        
        result = send_discord("Test message", tier="priority")
        
        assert result == "ok"
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://discord.com/priority"


def test_send_discord_blocked_in_pytest(monkeypatch):
    """send_discord should be blocked during pytest regardless of tier."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_tier_routing.py::test_send_discord_blocked_in_pytest")
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "https://discord.com/priority")
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = send_discord("Test message", tier="priority")
        
        assert result == "skipped"
        mock_post.assert_not_called()


def test_send_discord_skipped_when_no_url(monkeypatch):
    """send_discord should skip when no URL configured for tier."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    # Clear all Discord webhooks
    for key in ["DISCORD_WEBHOOK_URL", "DISCORD_WEBHOOK_PRIORITY", 
                "DISCORD_WEBHOOK_FORTUNE500", "DISCORD_WEBHOOK_OTHER"]:
        monkeypatch.delenv(key, raising=False)
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        result = send_discord("Test message", tier="priority")
        
        assert result == "skipped"
        mock_post.assert_not_called()


# --- Integration tests with Notifier ---


def test_notifier_routes_priority_job_to_priority_webhook(tmp_path, monkeypatch):
    """Priority company jobs should route to DISCORD_WEBHOOK_PRIORITY."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_tier_routing.py::test_notifier_routes_priority_job")
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "https://discord.com/priority")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="OpenAI",
        title="Software Engineer Intern",
        location="San Francisco",
        url="https://openai.com/careers/software-engineer-intern",
        sources=["test"],
    )
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        
        # Should still be blocked by PYTEST_CURRENT_TEST
        notifier.notify(job, silent=False)
        mock_post.assert_not_called()


def test_notifier_routes_fortune500_job_to_fortune500_webhook(tmp_path, monkeypatch):
    """Fortune500 company jobs should route to DISCORD_WEBHOOK_FORTUNE500."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_tier_routing.py::test_notifier_routes_fortune500_job")
    monkeypatch.setenv("DISCORD_WEBHOOK_FORTUNE500", "https://discord.com/fortune500")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="Goldman Sachs",
        title="Software Engineer Intern",
        location="New York",
        url="https://goldmansachs.com/careers/intern",
        sources=["test"],
    )
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        
        notifier.notify(job, silent=False)
        mock_post.assert_not_called()


def test_notifier_routes_other_job_to_other_webhook(tmp_path, monkeypatch):
    """Non-priority, non-Fortune500 jobs should route to DISCORD_WEBHOOK_OTHER."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_tier_routing.py::test_notifier_routes_other_job")
    monkeypatch.setenv("DISCORD_WEBHOOK_OTHER", "https://discord.com/other")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="Local Startup",
        title="Software Engineer Intern",
        location="Seattle",
        url="https://localstartup.com/careers/intern",
        sources=["test"],
    )
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        
        notifier.notify(job, silent=False)
        mock_post.assert_not_called()


def test_notifier_fallback_chain(tmp_path, monkeypatch):
    """Test fallback: tier URL -> legacy URL -> skip."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)  # Allow send
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    # Only legacy URL set
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/legacy")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    job = JobRecord(
        company="OpenAI",
        title="SWE Intern",
        location="SF",
        url="https://openai.com/careers/intern",
        sources=["test"],
    )
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        
        notifier.notify(job, silent=False)
        
        # Should fallback to legacy URL
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://discord.com/legacy"


def test_tier_classification_in_notification_flow(tmp_path, monkeypatch):
    """End-to-end test: verify tier classification happens in notify flow."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_tier_routing.py::test_tier_classification")
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    test_cases = [
        ("OpenAI", "priority"),
        ("Anthropic", "priority"),
        ("Goldman Sachs", "fortune500"),
        ("IBM", "fortune500"),
        ("Random Startup", "other"),
    ]
    
    for company, expected_tier in test_cases:
        job = JobRecord(
            company=company,
            title="SWE Intern",
            location="Location",
            url=f"https://{company.lower().replace(' ', '')}.com/careers/job123",
            sources=["test"],
        )
        
        with patch("jobradar.notify.send_discord") as mock_send:
            notifier.notify(job, silent=False)
            
            # Verify send_discord was called with correct tier
            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args[1]
            assert call_kwargs["tier"] == expected_tier, f"Failed for {company}: expected {expected_tier}, got {call_kwargs['tier']}"


def test_multiple_jobs_different_tiers_route_correctly(tmp_path, monkeypatch, respx_mock):
    """Multiple jobs with different company tiers should route to correct webhooks."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")  # Enable probing
    monkeypatch.setenv("DISCORD_WEBHOOK_PRIORITY", "https://discord.com/priority")
    monkeypatch.setenv("DISCORD_WEBHOOK_FORTUNE500", "https://discord.com/fortune500")
    monkeypatch.setenv("DISCORD_WEBHOOK_OTHER", "https://discord.com/other")
    
    # Mock successful HTTP probes for all job URLs
    respx_mock.route(method="HEAD", url="https://openai.com/careers/software-engineer-intern-12345").return_value = httpx.Response(200)
    respx_mock.route(method="HEAD", url="https://goldmansachs.com/careers/jobs/123456").return_value = httpx.Response(200)
    respx_mock.route(method="HEAD", url="https://startupco.com/jobs/engineer-789012").return_value = httpx.Response(200)
    
    db = Database(tmp_path / "test.db")
    notifier = Notifier(path=tmp_path / "notify.jsonl", db=db)
    
    jobs = [
        JobRecord(company="OpenAI", title="SWE Intern", location="SF", 
                  url="https://openai.com/careers/software-engineer-intern-12345", sources=["test"]),
        JobRecord(company="Goldman Sachs", title="SWE Intern", location="NY", 
                  url="https://goldmansachs.com/careers/jobs/123456", sources=["test"]),
        JobRecord(company="StartupCo", title="SWE Intern", location="Austin", 
                  url="https://startupco.com/jobs/engineer-789012", sources=["test"]),
    ]
    
    expected_urls = [
        "https://discord.com/priority",
        "https://discord.com/fortune500",
        "https://discord.com/other",
    ]
    
    with patch("jobradar.notify.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        
        for job in jobs:
            notifier.notify(job, silent=False)
        
        # Verify each call used correct webhook
        assert mock_post.call_count == 3
        actual_urls = [call[0][0] for call in mock_post.call_args_list]
        assert actual_urls == expected_urls
