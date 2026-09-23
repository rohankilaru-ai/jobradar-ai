# JobRadar-AI — Handoff for Cursor (post-MVP)

**Repo:** https://github.com/rohankilaru-ai/jobradar-ai  
**Local:** `/Users/rohankilaru/Resume Bot/job-agent-notifier/`  
**Branch:** `main`

## Latest: Overnight #41 — URL/Alert-Quality Harden — COMPLETE

**Goal:** Tighten empty/placeholder/`example.com` (and similar fixture/dummy) URL gates end-to-end so bad/fixture URLs never reach Discord/ntfy/Telegram — including the company-name↔host match bypass beyond overnight #8/#9/#28.

**Completed:**
- **Shared fixture helper** `is_fixture_or_dummy_url` in `src/jobradar/models.py` (suffix-safe host match so `contest.com` ≠ `test.com`)
- **Notify gate** `job_notify_block_reason` now blocks all fixture/dummy hosts with `fixture/dummy URL: …` *before* domain-match / specificity checks (closes company=`Test` + `test.com` / `Example` + `example.net` / `Localhost` bypass)
- **`is_url_quality_good`** aligned to the shared helper; expanded `BAD_URL_PATTERNS` (`example.net`, `test.org`, `0.0.0.0`, …)
- **`probe_url`** short-circuits fixture hosts locally (no HTTP — `example.com` can return 200)
- **Parser ingest** still strips fixtures via `is_bad_url` → empty URL; regression covered
- **Tests:** `tests/test_url_alert_quality_harden.py` + probe mocks retargeted off fixture hosts; CLI smoke test no longer treats `example.com` as a "valid URL"
- **PR #23 left untouched** (Gmail pack). No live Discord/ntfy/Telegram sends this cycle.

**Branch:** `overnight/41-url-alert-quality-harden`

**Next suggested:** Product-completion tests (end-to-end product acceptance / completion coverage). Do NOT re-suggest URL/alert-quality harden, parser HTML/URL harden #28, classification recall, notify-window, classify-exclude, or scout-health (already landed).

## Latest prior: Overnight #39/#40 — Classification Recall + Stack Hygiene — COMPLETE

## Latest prior: Overnight #39/#40 — Classification Recall + Stack Hygiene — COMPLETE

**Goal:** Land overnight #39 classification-recall feature (PR #57) and clear stack hygiene: close superseded PR #22; leave Gmail PR #23 untouched; refresh this handoff so Next no longer points at classification recall.

**Completed:**
- **PR #57 merged** ("Overnight #39: Classification recall for borderline technical roles") — squash-merged to main (`b2f9e9b`)
- **PR #22 closed** ("Remove Discord per-scan alert cap") — superseded by PR #40; commented + closed, not merged
- **PR #23 left open untouched** (Gmail/Notion inbox pack — Phase 4; standing skip)
- **Local Mac checkout** fast-forwarded to `origin/main` at `b2f9e9b`
- **Test suite at merge:** 643 tests passing (+11 classification-recall smokes)

**Branch:** `cursor/overnight-39-classification-recall-d530` (PR #57) → squash-merged to main (`b2f9e9b`)

**PR merged:**
- **PR #55** already on main (overnight #37 scout health) via overnight #38 hygiene
- **PR #57** ("Overnight #39: Classification recall…") — `strong_signals` overrides for Technical Account Manager / Technical Product Manager so exclude-list patterns do not drop borderline technical roles; 11 new tests in `tests/test_classify_dedupe_notify.py`

**Remaining open PRs:**
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).
- **PR #22** — CLOSED (superseded by #40).

**Main tip after this hygiene:** `b2f9e9b` (was `ca49f86` / HANDOFF #56 before #57).

**Next suggested:** URL/alert-quality harden — tighten empty/placeholder/`example.com` gates end-to-end (parser ingest + notify block reasons + regression tests) so bad/fixture URLs never reach Discord/ntfy/Telegram even when parsers or upstream HTML drift. Prefer test-driven gaps beyond overnight #8/#9/#28 already-landed coverage. Do NOT suggest already-landed work (classification recall, notify-window, classify-exclude, scout-health, parser HTML/URL harden #28).

## Latest prior: Overnight #38 — Merge/Stack Hygiene (PR #55) — COMPLETE

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
