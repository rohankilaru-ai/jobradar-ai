"""Overnight #53: HANDOFF stack-hygiene drift locks after PR #61 merge."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")


def _latest_section() -> str:
    return HANDOFF.split("## Latest prior:", 1)[0]


def test_handoff_latest_is_overnight_53_hygiene() -> None:
    assert "## Latest: Overnight #53" in HANDOFF
    assert "PR #61" in HANDOFF
    assert "271d6ed" in HANDOFF


def test_handoff_product_complete_yes_on_main() -> None:
    latest = _latest_section()
    assert "Product-complete signal: Yes" in latest
    assert "squash-merged" in latest.lower() or "MERGED" in latest
    # Stale blocker phrasing must not claim push is still needed
    assert "branch not pushed" not in latest.lower()
    assert "local only until Mac push" not in latest


def test_handoff_still_protects_pr_23() -> None:
    latest = _latest_section()
    assert "PR #23" in latest
    assert "untouched" in latest.lower()
