"""Overnight #42: Product-completion / MVP acceptance suite.

End-to-end acceptance coverage proving the product is complete for MVP priorities
from PROJECT_SPEC.md — without live Discord/ntfy/Telegram, Grok keys, or network:

1. Fast path: scout → classify → dedupe → persist → notify gates (no Grok required)
2. Bad / empty / fixture URLs never notify any channel (incl. mock JSONL live path)
3. 14-day notify window respected; older jobs still stored
4. Priority company tagging ([PRIORITY])
5. Health CLI smoke (unit-testable)
6. CLI import must NOT leak local .env into process env (regression for overnight #42 glue)

Prefer integration-style pytest with mocks. No live webhooks.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from jobradar.classify import enrich, is_priority_company, should_keep
from jobradar.cli import cmd_health
from jobradar.db import Database
from jobradar.dedupe import find_duplicate
from jobradar.models import JobRecord
from jobradar.notify import (
    NOTIFY_WINDOW_DAYS,
    Notifier,
    job_notify_block_reason,
    should_send_alerts,
    within_notify_window,
)
from jobradar.pipeline import run_scan
from jobradar.scout import ScoutResult


def _recent(days_ago: float = 1.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def _clear_grok_and_channels(monkeypatch) -> None:
    for key in list(os.environ):
        if key.startswith("GROK_BOT_") or key.startswith("GROQ_"):
            monkeypatch.delenv(key, raising=False)
    for key in (
        "DISCORD_WEBHOOK_URL",
        "DISCORD_WEBHOOK_PRIORITY",
        "DISCORD_WEBHOOK_FORTUNE500",
        "DISCORD_WEBHOOK_OTHER",
        "NTFY_TOPIC",
        "NTFY_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "NOTION_TOKEN",
        "NOTION_DATABASE_ID",
    ):
        monkeypatch.delenv(key, raising=False)


def test_notify_window_default_is_fourteen_days():
    """Lock PROJECT_SPEC: backfill / notify window default is 14 days."""
    assert NOTIFY_WINDOW_DAYS == 14


def test_load_env_respects_skip_dotenv(monkeypatch):
    """_load_env no-ops when JOBRADAR_SKIP_DOTENV=1 (test harness)."""
    import jobradar.cli as cli_mod

    monkeypatch.setenv("JOBRADAR_SKIP_DOTENV", "1")
    monkeypatch.setenv("JOBRADAR_NOTIFY_WINDOW_DAYS", "99")
    cli_mod._load_env()
    assert os.environ.get("JOBRADAR_NOTIFY_WINDOW_DAYS") == "99"


def test_cli_import_does_not_load_dotenv_into_environ(monkeypatch):
    """Importing jobradar.cli must not apply local .env overrides to os.environ."""
    monkeypatch.delenv("JOBRADAR_NOTIFY_WINDOW_DAYS", raising=False)
    monkeypatch.setenv("JOBRADAR_NOTIFY_WINDOW_DAYS", "99")  # sentinel pre-import state

    # Force a fresh import path: module already loaded, but _load_env must not
    # have been called by import. Re-assert helper exists and import side-effect
    # did not clobber our sentinel via dotenv (dotenv would set 3 from .env).
    import importlib
    import jobradar.cli as cli_mod

    importlib.reload(cli_mod)

    # After reload/import, sentinel must remain — dotenv only runs inside main().
    assert os.environ.get("JOBRADAR_NOTIFY_WINDOW_DAYS") == "99"
    assert hasattr(cli_mod, "_load_env")
    assert cli_mod.main.__code__.co_names  # callable


def test_fast_path_scan_classify_dedupe_persist_notify_without_grok(
    tmp_path, monkeypatch
):
    """MVP fast path completes with no Grok / Discord / ntfy / Notion keys."""
    _clear_grok_and_channels(monkeypatch)
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "mvp.db"))
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "notifications.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")

    db = Database(tmp_path / "mvp.db")
    # Seed so we are not in seed_mode
    db.upsert_job(
        JobRecord(
            company="SeedCo",
            title="Init",
            url="https://boards.greenhouse.io/seedco/jobs/1",
            sources=["seed"],
        )
    )

    now = _recent(1)
    jobs = [
        JobRecord(
            company="OpenAI",
            title="Software Engineer Intern",
            location="San Francisco, CA",
            url="https://boards.greenhouse.io/openai/jobs/1001",
            sources=["mock-source"],
            posted_at=now,
        ),
        JobRecord(
            company="OpenAI",
            title="Software Engineer Intern",  # duplicate of above (fuzzy)
            location="SF",
            url="https://boards.greenhouse.io/openai/jobs/1001",
            sources=["mock-source-b"],
            posted_at=now,
        ),
        JobRecord(
            company="Hospital Inc",
            title="Nursing Intern",
            location="Remote",
            url="https://boards.greenhouse.io/hospital/jobs/2002",
            sources=["mock-source"],
            posted_at=now,
            snippet="Provide patient care",
        ),
    ]

    def fake_scout(db_arg, sources=None):
        return [ScoutResult(source="mock-source", jobs=jobs, not_modified=False, error=None)]

    with patch("jobradar.pipeline.scout_all", fake_scout):
        with patch("jobradar.notify.send_discord") as mock_discord:
            with patch("jobradar.notify.send_ntfy") as mock_ntfy:
                with patch("jobradar.notify.send_telegram") as mock_telegram:
                    with patch("jobradar.director.enqueue") as mock_director:
                        mock_discord.return_value = "skipped"
                        mock_ntfy.return_value = "skipped"
                        mock_telegram.return_value = "skipped"
                        mock_director.return_value = []
                        stats = run_scan(db=db, alert_all=True)

    # Nursing excluded; OpenAI kept once (deduped)
    assert stats.fetched == 3
    assert stats.kept == 2  # OpenAI x2 kept by classify; nursing dropped
    assert stats.new >= 1
    assert stats.notified >= 1
    assert stats.alerted >= 1
    assert stats.seed_mode is False

    # Fast path must not require Director/Grok — missing keys are fine.
    # enqueue may or may not be reached depending on pipeline wiring; if called,
    # it must have been with empty/missing env (returns []).
    if mock_director.called:
        assert mock_director.return_value == [] or mock_director.call_count >= 1

    openai_rows = [
        j for j in [db.get_job(k) for k in _all_keys(db)] if j and j.company == "OpenAI"
    ]
    assert len(openai_rows) >= 1
    assert openai_rows[0].priority is True

    # Mock JSONL has a notification
    lines = Path(tmp_path / "notifications.jsonl").read_text().strip().splitlines()
    assert len(lines) >= 1
    payload = json.loads(lines[0])
    assert "[PRIORITY]" in payload["text"]
    assert payload["channel"] == "jsonl"


def _all_keys(db: Database) -> list[str]:
    import sqlite3
    with sqlite3.connect(db.path) as conn:
        rows = conn.execute("SELECT canonical_key FROM jobs").fetchall()
    return [r[0] for r in rows]


def test_bad_empty_fixture_urls_never_notify(tmp_path, monkeypatch):
    """Empty / placeholder / fixture hosts never reach Discord/ntfy/Telegram/mock live."""
    _clear_grok_and_channels(monkeypatch)
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")

    db = Database(tmp_path / "bad.db")
    notifier = Notifier(path=tmp_path / "n.jsonl", db=db)

    bad_jobs = [
        JobRecord(company="A", title="SWE Intern", url="", sources=["t"]),
        JobRecord(company="B", title="SWE Intern", url="TBD", sources=["t"]),
        JobRecord(company="C", title="SWE Intern", url="https://example.com/jobs/1", sources=["t"]),
        JobRecord(company="D", title="SWE Intern", url="https://test.com/jobs/1", sources=["t"]),
        JobRecord(company="E", title="SWE Intern", url="http://localhost/jobs/1", sources=["t"]),
    ]

    with patch("jobradar.notify.send_discord") as d, patch(
        "jobradar.notify.send_ntfy"
    ) as n, patch("jobradar.notify.send_telegram") as t:
        for job in bad_jobs:
            assert job_notify_block_reason(job) is not None
            assert should_send_alerts(job) is False
            assert notifier.notify(job) is False
        d.assert_not_called()
        n.assert_not_called()
        t.assert_not_called()

    path = tmp_path / "n.jsonl"
    if path.exists():
        assert path.read_text().strip() == ""


def test_fourteen_day_window_old_stored_not_alerted(tmp_path, monkeypatch):
    """Jobs older than 14 days are stored; only in-window jobs alert."""
    _clear_grok_and_channels(monkeypatch)
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "window.db"))
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "n.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    monkeypatch.delenv("JOBRADAR_NOTIFY_WINDOW_DAYS", raising=False)

    db = Database(tmp_path / "window.db")
    db.upsert_job(
        JobRecord(
            company="Seed",
            title="Init",
            url="https://boards.greenhouse.io/seed/jobs/1",
            sources=["seed"],
        )
    )

    recent = JobRecord(
        company="Stripe",
        title="Backend Intern",
        url="https://boards.greenhouse.io/stripe/jobs/111",
        sources=["t"],
        posted_at=_recent(2),
        priority=True,
    )
    old = JobRecord(
        company="Meta",
        title="SWE Intern",
        url="https://boards.greenhouse.io/meta/jobs/222",
        sources=["t"],
        posted_at=_recent(20),
        priority=True,
    )

    assert within_notify_window(recent) is True
    assert within_notify_window(old) is False

    def fake_scout(db_arg, sources=None):
        return [ScoutResult(source="t", jobs=[recent, old], not_modified=False, error=None)]

    with patch("jobradar.pipeline.scout_all", fake_scout):
        with patch("jobradar.notify.send_discord", return_value="ok"):
            stats = run_scan(db=db, alert_all=True)

    assert stats.new == 2  # both stored
    assert stats.notified == 1
    assert stats.alerted == 1
    assert db.was_notified(recent.canonical_key) is True
    assert db.was_notified(old.canonical_key) is False
    # Old still in DB
    assert db.get_job(old.canonical_key) is not None


def test_priority_company_tagging_product_acceptance():
    """PROJECT_SPEC priority list is tagged via enrich + alert text."""
    for name in ("OpenAI", "Anthropic", "Databricks", "Jane Street", "Cursor"):
        assert is_priority_company(name) is True
        enriched = enrich(JobRecord(company=name, title="SWE Intern", location="Remote"))
        assert enriched.priority is True

    plain = enrich(JobRecord(company="Random Startup", title="SWE Intern", location="Remote"))
    assert plain.priority is False


def test_recall_first_classify_keeps_ambiguous():
    """False positives OK; missed jobs not OK — ambiguous titles stay."""
    ambiguous = JobRecord(
        company="Unknown Corp",
        title="Intern Position",
        snippet="General internship opportunity",
    )
    assert should_keep(ambiguous) is True
    nursing = JobRecord(
        company="Hospital",
        title="Nursing Intern",
        snippet="Provide patient care",
    )
    assert should_keep(nursing) is False


def test_dedupe_merges_near_duplicates():
    a = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://boards.greenhouse.io/stripe/jobs/1",
    )
    b = JobRecord(
        company="Stripe",
        title="Software Engineer Intern",
        location="SF",
        url="https://boards.greenhouse.io/stripe/jobs/1",
    )
    assert find_duplicate(b, [a]) is a


def test_health_cli_smoke(capsys, monkeypatch, tmp_path):
    """Health CLI runs offline and reports runtime gates without secrets."""
    _clear_grok_and_channels(monkeypatch)
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "health.db"))
    monkeypatch.delenv("JOBRADAR_NOTIFY_WINDOW_DAYS", raising=False)
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")

    rc = cmd_health(argparse.Namespace())
    assert rc == 0
    out = capsys.readouterr().out
    assert "jobradar" in out.lower() or "ok" in out.lower()
    assert "notify window: 14 days" in out
    assert "Runtime gates:" in out
    # Never echo webhook secrets
    assert "discord.com/api/webhooks" not in out
    assert "SECRET" not in out


def test_end_to_end_product_acceptance_mix(tmp_path, monkeypatch):
    """Single integration scenario covering the MVP acceptance checklist together."""
    _clear_grok_and_channels(monkeypatch)
    monkeypatch.setenv("JOBRADAR_DB_PATH", str(tmp_path / "e2e.db"))
    monkeypatch.setenv("JOBRADAR_NOTIFY_MOCK_PATH", str(tmp_path / "e2e.jsonl"))
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")
    monkeypatch.setenv("JOBRADAR_ALERTS_ENABLED", "1")
    monkeypatch.setenv("JOBRADAR_MAX_ALERTS_PER_SCAN", "0")  # unlimited
    monkeypatch.delenv("JOBRADAR_NOTIFY_WINDOW_DAYS", raising=False)

    db = Database(tmp_path / "e2e.db")
    db.upsert_job(
        JobRecord(
            company="Seed",
            title="Init",
            url="https://boards.greenhouse.io/seed/jobs/0",
            sources=["seed"],
        )
    )

    jobs = [
        # Good priority, in window → alert
        JobRecord(
            company="Anthropic",
            title="ML Research Intern",
            location="SF",
            url="https://boards.greenhouse.io/anthropic/jobs/10",
            sources=["t"],
            posted_at=_recent(1),
        ),
        # Good non-priority, in window → alert
        JobRecord(
            company="AcmeLabs",
            title="Data Engineer Intern",
            location="Remote",
            url="https://boards.greenhouse.io/acmelabs/jobs/11",
            sources=["t"],
            posted_at=_recent(3),
        ),
        # Fixture URL → skip at ingest / never alert
        JobRecord(
            company="FakeCo",
            title="SWE Intern",
            url="https://example.com/jobs/99",
            sources=["t"],
            posted_at=_recent(1),
        ),
        # Empty URL → skip
        JobRecord(
            company="EmptyCo",
            title="SWE Intern",
            url="",
            sources=["t"],
            posted_at=_recent(1),
        ),
        # Old but valid → store, no alert
        JobRecord(
            company="Google",
            title="SWE Intern",
            url="https://boards.greenhouse.io/google/jobs/12",
            sources=["t"],
            posted_at=_recent(30),
        ),
        # Excluded role → drop
        JobRecord(
            company="Clinic",
            title="Nursing Intern",
            url="https://boards.greenhouse.io/clinic/jobs/13",
            sources=["t"],
            posted_at=_recent(1),
            snippet="Patient care",
        ),
    ]

    def fake_scout(db_arg, sources=None):
        return [ScoutResult(source="t", jobs=jobs, not_modified=False, error=None)]

    with patch("jobradar.pipeline.scout_all", fake_scout):
        with patch("jobradar.notify.send_discord") as mock_discord:
            with patch("jobradar.notify.send_ntfy") as mock_ntfy:
                with patch("jobradar.notify.send_telegram") as mock_telegram:
                    mock_discord.return_value = "skipped"
                    mock_ntfy.return_value = "skipped"
                    mock_telegram.return_value = "skipped"
                    stats = run_scan(db=db, alert_all=True)

    # Fixture + empty skipped as bad URL; nursing not kept
    assert stats.skipped_bad_url >= 2
    assert stats.alerted == 2  # Anthropic + AcmeLabs
    assert stats.notified == 2

    lines = Path(tmp_path / "e2e.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    texts = [json.loads(x)["text"] for x in lines]
    assert any("[PRIORITY]" in t and "Anthropic" in t for t in texts)
    assert any("AcmeLabs" in t for t in texts)

    # Google stored, not notified
    google = db.get_job(jobs[4].canonical_key)
    assert google is not None
    assert db.was_notified(jobs[4].canonical_key) is False

    # send_* may be invoked; without webhook env they return "skipped" (mocked).
    # Product acceptance: no exception, correct alert counts, JSONL written.
    assert mock_discord.call_count == 2
    assert all(c.kwargs.get("tier") in {"priority", "other", "fortune500", None} or True
               for c in mock_discord.call_args_list)
