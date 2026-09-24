"""Overnight #45: Product-complete review locks for PROJECT_SPEC claims
that prior acceptance suites did not pin explicitly.

Prefer asserting existing behavior (Docker files, schema, alert shape,
source catalog, CLI registration) — no product rewrites, no Gmail.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jobradar.cli import build_parser
from jobradar.db import Database
from jobradar.models import JobRecord
from jobradar.notify import format_alert
from jobradar.sources import SOURCES

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_matches_project_spec():
    """PROJECT_SPEC Docker: python:3.12-slim + volume for ./data."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    assert "FROM python:3.12-slim" in dockerfile
    assert "VOLUME" in dockerfile
    assert "/app/data" in dockerfile or "./data" in dockerfile


def test_docker_compose_mounts_data_volume():
    """Compose should mount host ./data into the container data path."""
    compose = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "./data:/app/data" in compose or "./data:" in compose


def test_sqlite_schema_has_project_spec_tables(tmp_path):
    """PROJECT_SPEC tables: jobs, job_sources, notifications, agent_runs,
    fetch_cache; stubs emails, applications. Unique on jobs.canonical_key.
    """
    db = Database(tmp_path / "schema.db")
    with sqlite3.connect(db.path) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {
            "jobs",
            "job_sources",
            "notifications",
            "agent_runs",
            "fetch_cache",
            "emails",
            "applications",
        }.issubset(names)

        pk = conn.execute("PRAGMA table_info(jobs)").fetchall()
        # cid, name, type, notnull, dflt, pk
        key_cols = [r[1] for r in pk if r[5]]
        assert key_cols == ["canonical_key"]


def test_format_alert_matches_project_spec_shape():
    """Lock alert layout from PROJECT_SPEC (priority prefix + 3 header lines + blank + summary)."""
    job = JobRecord(
        company="OpenAI",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://boards.greenhouse.io/openai/jobs/1001",
        sources=["simplify-summer-2027"],
        snippet="Build models.\nShip carefully.\nIgnored third line.",
        priority=True,
    )
    text = format_alert(job)
    lines = text.splitlines()
    assert lines[0] == "[PRIORITY] OpenAI"
    assert lines[1] == "Software Engineer Intern | San Francisco, CA"
    assert lines[2] == (
        "simplify-summer-2027 | https://boards.greenhouse.io/openai/jobs/1001"
    )
    assert lines[3] == ""
    assert lines[4] == "Build models."
    assert lines[5] == "Ship carefully."
    assert "Ignored third line." not in text


def test_mvp_source_catalog_contains_required_repos():
    """PROJECT_SPEC MVP sources (internship set) must be present; pittcsc never."""
    urls = " ".join(s.url for s in SOURCES).lower()
    required_fragments = [
        "aprameyak/2027-tech-jobs",
        "dreamworkhq/tech-internships-2027",
        "applyguy/2027-internships",
        "simplifyjobs/summer2027-internships/dev/readme.md",
        "simplifyjobs/summer2027-internships/dev/readme-off-season.md",
        "vanshb03/summer2027-internships",
        "speedyapply/2027-swe-college-jobs/main/readme.md",
        "speedyapply/2027-swe-college-jobs/main/intern_intl.md",
        "speedyapply/2027-ai-college-jobs/main/readme.md",
        "speedyapply/2027-ai-college-jobs/main/intern_intl.md",
    ]
    for frag in required_fragments:
        assert frag in urls, f"Missing MVP source fragment: {frag}"

    assert "pittcsc" not in urls
    # Intentional product choice (internships-only): New-Grad Positions not active
    assert "new-grad-positions" not in urls
    assert "new_grad" not in urls


def test_cli_registers_project_spec_commands():
    """PROJECT_SPEC CLI: scan (--once/--loop), health, ping-grok."""
    parser = build_parser()
    # Top-level subcommands
    sub_actions = [
        a for a in parser._actions if getattr(a, "dest", None) == "command" or hasattr(a, "choices")
    ]
    # argparse stores subparsers on a private action; parse known good argv instead
    scan_once = parser.parse_args(["scan", "--once"])
    assert scan_once.once is True
    scan_loop = parser.parse_args(["scan", "--loop", "--interval", "300"])
    assert scan_loop.loop is True
    assert scan_loop.interval == 300
    health = parser.parse_args(["health"])
    assert health.command == "health" or getattr(health, "func", None) is not None
    ping = parser.parse_args(["ping-grok"])
    assert ping.command == "ping-grok" or getattr(ping, "func", None) is not None


def test_director_timeout_is_eight_seconds():
    """PROJECT_SPEC slow path: Director POST timeout 8s."""
    import inspect

    import jobradar.director as director

    src = inspect.getsource(director)
    assert "timeout=8.0" in src or "timeout=8" in src
