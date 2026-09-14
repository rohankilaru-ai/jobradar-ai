"""Fuzzy dedupe helpers (rapidfuzz)."""

from __future__ import annotations

from rapidfuzz import fuzz

from jobradar.models import JobRecord


def similar(a: str, b: str) -> float:
    return float(fuzz.token_set_ratio((a or "").lower(), (b or "").lower()))


def is_duplicate(a: JobRecord, b: JobRecord, threshold: float = 80.0) -> bool:
    if a.canonical_key and a.canonical_key == b.canonical_key:
        return True
    if similar(a.company, b.company) < threshold:
        return False
    if similar(a.title, b.title) < threshold:
        return False
    # location soft: empty matches anything; abbreviations / containment OK
    if a.location and b.location:
        la, lb = a.location.lower().strip(), b.location.lower().strip()
        if la in lb or lb in la or min(len(la), len(lb)) <= 3:
            pass
        elif similar(a.location, b.location) < threshold:
            return False
    return True


def find_duplicate(job: JobRecord, existing: list[JobRecord], threshold: float = 80.0) -> JobRecord | None:
    for other in existing:
        if is_duplicate(job, other, threshold=threshold):
            return other
    return None
