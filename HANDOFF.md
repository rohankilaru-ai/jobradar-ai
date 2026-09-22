# JobRadar-AI — Handoff for Cursor (post-MVP)

**Repo:** https://github.com/rohankilaru-ai/jobradar-ai  
**Local:** `/Users/rohankilaru/Resume Bot/job-agent-notifier/`  
**Branch:** `main`

## Latest: Overnight #38 — Merge/Stack Hygiene (PR #55) — COMPLETE

**Goal:** Merge/stack hygiene for overnight #37 draft PR #55 onto main. No new feature work. Mirror overnight #31/#34/#36 pattern.

**Completed:**
- **PR #55 merged** ("Overnight #37: Scout health age/staleness surfacing")
- **PR marked ready** for review (converted from draft)
- **Resolved HANDOFF.md merge conflict** after PR #54 landed (merged origin/main into PR branch, cleaned conflict markers)
- **Full pytest green** before merge (all 632 tests passing ✅)
- **Main tip after overnight #38:** 6ebf952 (was 42f5b51 before overnight #38)

**Branch:** `cursor/overnight-37-scout-health-staleness-96a2` (PR #55) → squash-merged to main (6ebf952)

**PR merged:**
- **PR #55** ("Overnight #37: Scout health age/staleness surfacing") — Added source health age/staleness observability to `health` CLI. Database enhancements for age calculation, staleness detection (3-day default threshold), fresh/stale classification. CLI shows stale sources and never-fetched sources. 10 new tests in test_scout_health.py. All 632 tests passing after merge.

**Remaining open PRs:**
- **PR #22** ("Remove Discord per-scan alert cap") — superseded by PR #40 (unlimited alert cap default). Leave for user to close.
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).

**Next suggested:** Classification recall improvements — review classify.py exclusion logic for borderline technical roles that may be incorrectly filtered (e.g., "Product Engineer", "Technical Program Manager", "Solutions Engineer"). Current exclude-list (overnight #32 / PR #50) is extensive; consider adding smoke tests for specific borderline titles to prevent false negatives. Non-Gmail, test-driven, improves notification recall. Do NOT suggest already-landed work (notify-window, classify-exclude, scout-health items are done).

## Latest prior: Overnight #37 — Scout Health Age/Staleness Surfacing (PR #55) — LANDED

**Branch:** `cursor/overnight-37-scout-health-staleness-96a2` → squash-merged to main (6ebf952)

**Goal:** Add observability for source health **age** (time since last successful fetch) and **staleness** (sources not updated for >N days) in `python -m jobradar health` output so operators can spot dead/quiet sources without manual spot-checks. Build on overnight #33 / PR #51 scout_health foundation.

**Completed:**
- **Database enhancements** (`src/jobradar/db.py`): `SCOUT_HEALTH_STALENESS_THRESHOLD_DAYS = 3` constant, `get_scout_health_with_age()` method for age calculation, staleness detection, `_format_age()` helper
- **Health CLI enhancements** (`src/jobradar/cli.py`): Age/staleness summary, stale sources list, never-fetched sources list, preserved error display
- **Edge cases**: Only ok/not_modified count as fresh, never-fetched detection, threshold boundaries, empty history handling
- **Tests:** 10 new tests in `tests/test_scout_health.py` — fresh/stale/boundary/mixed/custom threshold/no history/age formatting/CLI display
- **All 632 tests passing** ✅

**Status:** Squash-merged to main (6ebf952) as part of overnight #38 stack hygiene.

## Latest prior: Overnight #36 — Merge/Stack Hygiene (PR #53/#54) — COMPLETE

**Goal:** Merge/stack hygiene for overnight #35 draft PR #53 onto main. No new feature work. Mirror overnight #31/#34 pattern.

**Completed:**
- **PR #53 merged** ("Overnight #35: Audit and normalize notify window docs drift")
- **PR #54 merged** (HANDOFF update after #53)
- **PR marked ready** for review (converted from draft)
- **Resolved merge conflict** in HANDOFF.md (merged main into PR branch, resolved cleanly)
- **CI green** before merge (test check SUCCESS)
- **Test suite:** All 622 tests passing ✅
- **Main tip after overnight #36:** 42f5b51 (was 8a84e86 before overnight #36)

**Branch:** `cursor/overnight-36-handoff-update-1cbe` (PR #54) → squash-merged to main (42f5b51)

**PR merged:**
- **PR #53** ("Overnight #35: Audit and normalize notify window docs drift (3-day → 14-day)") — Fixed docs/workflows to match canonical 14-day default, added 4 drift-lock tests, 622 tests passing after merge

**Remaining open PRs (at time of overnight #36 completion):**
- **PR #22** ("Remove Discord per-scan alert cap") — superseded by PR #40 (unlimited alert cap default). Leave for user to close.
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).
