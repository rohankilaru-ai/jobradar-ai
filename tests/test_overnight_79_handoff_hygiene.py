"""Overnight #79: HANDOFF hygiene drift locks after PR #66 merge (loop resumed)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")


def _latest_section() -> str:
    return HANDOFF.split("## Latest prior:", 1)[0]


def test_handoff_latest_is_overnight_79_hygiene() -> None:
    latest = _latest_section()
    assert "## Latest: Overnight #79" in HANDOFF
    assert "PR #66" in latest
    assert "d688b6ee" in latest
    assert "squash-merged" in latest.lower()


def test_handoff_records_loop_resumed() -> None:
    latest = _latest_section()
    assert "2026-09-28" in latest
    assert "resumed" in latest.lower()


def test_handoff_next_is_rohan_ops_only() -> None:
    latest = _latest_section()
    assert "webhook" in latest.lower()
    assert "secrets" in latest.lower()
    assert "Do NOT invent overnight feature work" in latest


def test_handoff_product_complete_yes_and_pr23_untouched() -> None:
    latest = _latest_section()
    assert "Product-complete signal: Yes" in latest
    assert "PR #23" in latest
    assert "untouched" in latest.lower()
    assert "branch not pushed" not in latest.lower()
