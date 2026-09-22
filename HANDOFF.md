# JobRadar-AI — Handoff for Cursor (post-MVP)

**Repo:** https://github.com/rohankilaru-ai/jobradar-ai  
**Local:** `/Users/rohankilaru/Resume Bot/job-agent-notifier/`  
**Branch:** `main`

## Latest: Overnight #37 — Scout Health Age/Staleness Surfacing (PR #55) — IN PROGRESS

**Branch:** `cursor/overnight-37-scout-health-staleness-96a2` → draft PR #55 open  
**Commit:** 6e79837

**Goal:** Add observability for source health **age** (time since last successful fetch) and **staleness** (sources not updated for >N days) in `python -m jobradar health` output so operators can spot dead/quiet sources without manual spot-checks. Build on overnight #33 / PR #51 scout_health foundation.

**Completed:**
- **Database enhancements** (`src/jobradar/db.py`):
  - Added `SCOUT_HEALTH_STALENESS_THRESHOLD_DAYS = 3` constant (configurable default)
  - New method `get_scout_health_with_age(staleness_threshold_days)` calculates age since last successful fetch (ok/not_modified only)
  - Staleness detection (age > threshold), fresh/stale classification
  - Helper function `_format_age(seconds)` for human-readable age display (e.g., "5d 2h", "1d")
- **Health CLI enhancements** (`src/jobradar/cli.py`):
  - Age/staleness summary section (fresh count, stale count, never-fetched count)
  - Stale sources list when any exist (name, age, last fetch timestamp)
  - Never-fetched sources list (sources in catalog but no history)
  - Preserved existing error display
- **Edge cases handled**:
  - Only ok/not_modified count as fresh; recent errors don't reset staleness
  - Never-fetched sources identified by comparing SOURCES catalog with history
  - Threshold boundaries tested (at/just over/just under 3 days)
  - Empty history / no sources handled cleanly
- **Tests:** 10 new tests in `tests/test_scout_health.py`
  - Fresh/stale/boundary/mixed status/last successful fetch/custom threshold/no history
  - Age formatting helpers
  - CLI display with staleness info
  - All 632 tests passing ✅
- **Draft PR #55** created with full documentation

**Pre-step completed:** PR #54 (overnight #36 HANDOFF update) converted to ready and squash-merged onto main (42f5b51).

**Main tip after overnight #37 work:** 6e79837 (on feature branch; main at 42f5b51 until PR #55 merged)

**Remaining open PRs:**
- **PR #55** ("Overnight #37: Scout health age/staleness") — this work, draft PR open, ready for review
- **PR #22** ("Remove Discord per-scan alert cap") — superseded by PR #40 (unlimited alert cap default). Leave for user to close.
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).

**Next suggested:** Classification recall improvements — review classify.py exclusion logic for borderline technical roles that may be incorrectly filtered (e.g., "Product Engineer", "Technical Program Manager", "Solutions Engineer"). Current exclude-list (overnight #32 / PR #50) is extensive; consider adding smoke tests for specific borderline titles to prevent false negatives. Non-Gmail, test-driven, improves notification recall.

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

**Next suggested (from overnight #36):** Scout health age/staleness surfacing — Add observability for source health age (time since last successful fetch) and staleness detection (sources not updated for N days) to `health` CLI output and potentially alert on stale sources. Would help identify sources that may need attention or removal before they silently fail. Non-Gmail, builds on overnight #33 scout_health foundation.

## Latest prior: Overnight #35 — Notify Window Docs Drift Audit (PR #53) — LANDED
