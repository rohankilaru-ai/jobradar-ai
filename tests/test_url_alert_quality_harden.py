"""Overnight #41: URL/alert-quality harden beyond #8/#9/#28.

Gap closed: fixture/dummy hosts (example.net, test.com, localhost, …) used to
slip past job_notify_block_reason when the company name loosely matched the
host (domain_matches_company True). Discord/ntfy/Telegram must never fire for
those URLs. Probe must short-circuit fixtures without HTTP (example.com → 200).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from jobradar.models import JobRecord, is_bad_url, is_fixture_or_dummy_url
from jobradar.link_probe import probe_url
from jobradar.notify import (
    Notifier,
    is_url_quality_good,
    job_notify_block_reason,
    should_send_alerts,
)
from jobradar.parsers import parse_simplify_html


FIXTURE_CASES = [
    "https://example.com/jobs/123",
    "https://www.example.com/apply/99",
    "https://example.org/careers/job/1",
    "https://example.net/jobs/abc",
    "https://test.com/jobs/123",
    "https://test.org/jobs/123",
    "http://localhost:3000/jobs/1",
    "http://127.0.0.1/jobs/1",
    "http://0.0.0.0/jobs/1",
    "https://placeholder.com/careers/role/1",
]


@pytest.mark.parametrize("url", FIXTURE_CASES)
def test_is_fixture_or_dummy_url_covers_hosts(url):
    assert is_fixture_or_dummy_url(url) is True
    assert is_bad_url(url) is True
    assert is_url_quality_good(url) is False


@pytest.mark.parametrize("url", FIXTURE_CASES)
def test_block_reason_fixture_even_when_company_matches_host(url, monkeypatch):
    """Company='Test' + test.com previously returned None — must block now."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    # Derive a company token that domain_matches_company accepts for the host
    host_guess = {
        "example.com": "Example",
        "example.org": "Example",
        "example.net": "Example",
        "test.com": "Test",
        "test.org": "Test",
        "localhost": "Localhost",
        "127.0.0.1": "127",
        "0.0.0.0": "0",
        "placeholder.com": "Placeholder",
    }
    company = "FixtureCo"
    for marker, name in host_guess.items():
        if marker in url:
            company = name
            break
    job = JobRecord(
        company=company,
        title="SWE Intern",
        location="SF",
        url=url,
        sources=["test"],
        posted_at="2026-09-20",
    )
    reason = job_notify_block_reason(job)
    assert reason is not None, f"expected block for {url} company={company}"
    assert "fixture" in reason.lower() or "dummy" in reason.lower() or "placeholder" in reason.lower() or "empty" in reason.lower()


@pytest.mark.parametrize("url", FIXTURE_CASES)
def test_should_send_alerts_false_for_fixtures(url, monkeypatch):
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    job = JobRecord(
        company="Test",  # matches test.com historically
        title="SWE Intern",
        location="SF",
        url=url,
        sources=["test"],
        posted_at="2026-09-20",
    )
    assert should_send_alerts(job) is False


@pytest.mark.parametrize("url", FIXTURE_CASES)
def test_notifier_never_hits_live_channels_for_fixtures(url, tmp_path, monkeypatch):
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    notifier = Notifier(path=tmp_path / "notify.jsonl")
    job = JobRecord(
        company="Test",
        title="SWE Intern",
        location="SF",
        url=url,
        sources=["test"],
        posted_at="2026-09-20",
    )
    with patch("jobradar.notify.send_discord") as d, patch(
        "jobradar.notify.send_ntfy"
    ) as n, patch("jobradar.notify.send_telegram") as t:
        assert notifier.notify(job) is False
        d.assert_not_called()
        n.assert_not_called()
        t.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/jobs/1",
        "https://example.net/jobs/2",
        "https://test.com/jobs/3",
        "http://localhost/jobs/4",
    ],
)
def test_probe_short_circuits_fixtures(url):
    assert probe_url(url) == "bad"


def test_parser_ingest_strips_fixture_urls_to_empty():
    html = """
    <table>
    <tr><td>Company</td><td>Role</td><td>Location</td><td>Application</td></tr>
    <tr><td>Acme</td><td>SWE Intern</td><td>SF</td>
        <td><a href="https://example.net/jobs/99">Apply</a></td></tr>
    <tr><td>Beta</td><td>SWE Intern</td><td>NYC</td>
        <td><a href="https://test.com/jobs/88">Apply</a></td></tr>
    <tr><td>Gamma</td><td>SWE Intern</td><td>Remote</td>
        <td><a href="https://boards.greenhouse.io/gamma/jobs/777">Apply</a></td></tr>
    </table>
    """
    jobs = parse_simplify_html(html)
    by_co = {j.company: j.url for j in jobs}
    assert by_co["Acme"] == ""
    assert by_co["Beta"] == ""
    assert by_co["Gamma"] == "https://boards.greenhouse.io/gamma/jobs/777"


def test_real_job_urls_still_pass_quality(monkeypatch):
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    job = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="SF",
        url="https://stripe.com/careers/jobs/software-engineer-intern-123456",
        sources=["test"],
        posted_at="2026-09-20",
    )
    assert is_fixture_or_dummy_url(job.url) is False
    assert is_url_quality_good(job.url) is True
    assert job_notify_block_reason(job) is None


def test_contest_com_not_false_flagged_as_test_com():
    """Suffix-safe: contest.com must not match the test.com fixture marker."""
    url = "https://contest.com/careers/jobs/swe-intern-42"
    assert is_fixture_or_dummy_url(url) is False
    assert is_url_quality_good(url) is True
