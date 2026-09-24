"""Overnight #46: Drift-lock PROJECT_SPEC to shipped product.

Locks that PROJECT_SPEC no longer requires SMS/Twilio as a deliverable,
positively names Discord/ntfy/Telegram, and treats New-Grad as optional /
out of internship-MVP (not a required source). Does not re-enable New-Grad
or invent Twilio.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = (REPO_ROOT / "PROJECT_SPEC.md").read_text()
REVIEW = (REPO_ROOT / "docs" / "PRODUCT_COMPLETE_REVIEW.md").read_text()


def test_project_spec_names_discord_ntfy_telegram_alert_channels():
    """PROJECT_SPEC fast-path alerts are Discord + ntfy + Telegram (+ mock)."""
    lower = SPEC.lower()
    assert "discord" in lower
    assert "ntfy" in lower
    assert "telegram" in lower
    assert "notifications.jsonl" in lower or "jsonl" in lower
    # Positive channel naming in fast-path / priorities section
    assert re.search(r"discord\s*/\s*ntfy\s*/\s*telegram|discord\s*\+\s*ntfy\s*\+\s*telegram", lower)


def test_project_spec_does_not_require_sms_or_twilio_as_deliverable():
    """SMS/Twilio must not be a required alert-channel deliverable.

    Mentions under Out of MVP (or explicit 'not used') are OK; required
    fast-path / priorities wording that 'owns SMS' or routes to SMS+Discord
    as the product path is not.
    """
    # Strip fenced code blocks lightly; focus on prose requirements
    lines = SPEC.splitlines()
    # Collect non-heading requirement-ish lines outside Out of MVP section
    in_out_of_mvp = False
    required_prose: list[str] = []
    for line in lines:
        if line.strip().startswith("## Out of MVP"):
            in_out_of_mvp = True
            continue
        if line.strip().startswith("## ") and in_out_of_mvp:
            in_out_of_mvp = False
        if in_out_of_mvp:
            continue
        required_prose.append(line)

    required_text = "\n".join(required_prose).lower()
    # Must not require SMS/Twilio in MVP deliverable sections
    assert "twilio" not in required_text, (
        "PROJECT_SPEC still names Twilio outside Out of MVP"
    )
    # "SMS" should not appear as a required channel in priorities/fast path
    assert not re.search(r"\bsms\b", required_text), (
        "PROJECT_SPEC still requires SMS outside Out of MVP"
    )


def test_project_spec_treats_new_grad_as_optional_not_required_mvp():
    """Simplify New-Grad must be optional / out-of-internship-MVP, not required."""
    lower = SPEC.lower()
    assert "new-grad-positions" in lower or "new-grad" in lower
    # Must explicitly mark optional / out of internship-MVP / disabled by default
    assert (
        "optional" in lower
        or "out of internship-mvp" in lower
        or "disabled by default" in lower
        or "not a required mvp source" in lower
    ), "PROJECT_SPEC must mark New-Grad optional / out-of-MVP"

    # Ensure New-Grad is NOT listed under the required Markdown MVP bullets
    # without optional framing: find the Sources (MVP) section and check
    # New-Grad appears under optional language, not as a bare required bullet.
    sources_match = re.search(
        r"## Sources \(MVP\)(.*?)(?:\n## |\Z)", SPEC, re.S | re.I
    )
    assert sources_match, "Missing Sources (MVP) section"
    sources_section = sources_match.group(1)
    # Required markdown list should not have a bare New-Grad bullet before Optional
    optional_split = re.split(
        r"\*\*Optional|\*\*optional|Optional / out", sources_section, maxsplit=1
    )
    required_part = optional_split[0].lower()
    assert "new-grad-positions" not in required_part, (
        "New-Grad still listed as a required MVP markdown source"
    )


def test_product_complete_review_signal_yes_after_spec_align():
    """After #46, review must claim product-complete Yes and cite #46 amendment."""
    assert re.search(
        r"Product-complete signal:?\s*\*?\*?Yes\*?\*?", REVIEW, re.I
    ), "Review must state Product-complete signal Yes"
    # Also lock the Verdict section
    assert re.search(r"Product-complete signal:\s*Yes", REVIEW, re.I)
    assert "#46" in REVIEW or "overnight #46" in REVIEW.lower()
    assert "amended" in REVIEW.lower() or "PROJECT_SPEC" in REVIEW


def test_product_complete_review_reclassifies_sms_and_newgrad_met():
    """SMS and New-Grad rows should be met (spec-aligned), not gap/partial."""
    # SMS row
    assert re.search(
        r"SMS\s*/\s*Twilio.*?\*\*met\*\*", REVIEW, re.S | re.I
    ) or ("spec-aligned" in REVIEW.lower() and "sms" in REVIEW.lower())
    # New-Grad claim
    assert re.search(
        r"New-Grad-Positions.*?\*\*met\*\*", REVIEW, re.S | re.I
    ) or ("spec-aligned optional" in REVIEW.lower())
    # Material gaps section should not list them as open gaps
    gaps = re.search(
        r"## Material gaps.*?(?:\n## |\Z)", REVIEW, re.S | re.I
    )
    assert gaps
    gaps_text = gaps.group(0).lower()
    assert "none remaining" in gaps_text or "resolved" in gaps_text
