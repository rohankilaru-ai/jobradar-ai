"""Overnight #43: live scan validation docs/harness drift locks + CLI smoke."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobradar.cli import cmd_validate_scan
from jobradar.notify import max_alerts_per_scan, NOTIFY_WINDOW_DAYS


REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_SCAN_DOC = REPO_ROOT / "docs" / "LIVE_SCAN_VALIDATION.md"


def test_live_scan_validation_doc_has_no_conflict_markers():
    text = LIVE_SCAN_DOC.read_text(encoding="utf-8")
    assert "<<<<<<<" not in text
    assert ">>>>>>>" not in text
    # Lone conflict separator (7 equals) on its own line — allow longer ==== rulers
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip() == "=======":
            pytest.fail(f"unresolved conflict separator at line {i}")


def test_live_scan_validation_doc_covers_key_claims():
    text = LIVE_SCAN_DOC.read_text(encoding="utf-8")
    required = [
        "Overnight #43",
        "is_fixture_or_dummy_url",
        "probe_deferred",
        "cap_deferred",
        "JOBRADAR_MAX_ALERTS_PER_SCAN",
        "priority-first",
        "validate-scan",
        "Technical Account Manager",
        "Technical Product Manager",
        "staleness",
        "14",
        "sources:",
    ]
    missing = [s for s in required if s not in text]
    assert not missing, f"LIVE_SCAN_VALIDATION.md missing claims: {missing}"


def test_max_alerts_default_unlimited_matches_docs():
    """Docs claim JOBRADAR_MAX_ALERTS_PER_SCAN default 0 = unlimited."""
    assert max_alerts_per_scan() == 0
    text = LIVE_SCAN_DOC.read_text(encoding="utf-8")
    assert "**Default:** `0` (unlimited)" in text


def test_notify_window_default_14_mentioned_in_docs():
    assert NOTIFY_WINDOW_DAYS == 14
    text = LIVE_SCAN_DOC.read_text(encoding="utf-8")
    assert "14" in text
    assert "JOBRADAR_NOTIFY_WINDOW_DAYS" in text


def test_validate_scan_cli_exits_zero(monkeypatch, capsys):
    """Harness must pass offline and restore JOBRADAR_LINK_PROBE."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "1")
    monkeypatch.setenv("JOBRADAR_SKIP_DOTENV", "1")
    monkeypatch.delenv("JOBRADAR_NOTIFY_WINDOW_DAYS", raising=False)
    monkeypatch.setenv("JOBRADAR_REQUIRE_POSTED_AT", "1")

    class NS:
        pass

    rc = cmd_validate_scan(NS())
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "Fixture/dummy URL gates validated" in out
    assert "All validation checks passed" in out
    # save/restore LINK_PROBE
    import os

    assert os.environ.get("JOBRADAR_LINK_PROBE") == "1"


def test_validate_scan_blocks_fixture_even_with_matching_company(monkeypatch, capsys):
    """Regression: company=Test + test.com must still be blocked in harness path."""
    monkeypatch.setenv("JOBRADAR_LINK_PROBE", "0")
    monkeypatch.setenv("JOBRADAR_SKIP_DOTENV", "1")

    class NS:
        pass

    rc = cmd_validate_scan(NS())
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "contest.com falsely flagged" not in out
