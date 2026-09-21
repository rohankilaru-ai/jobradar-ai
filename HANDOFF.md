# JobRadar-AI — Handoff for Cursor (post-MVP)

**Repo:** https://github.com/rohankilaru-ai/jobradar-ai  
**Local:** `/Users/rohankilaru/Resume Bot/job-agent-notifier/`  
**Branch:** `main`

<<<<<<< HEAD
## Latest: Overnight #22 — Default Unlimited Alert Cap (PR #40) — SHIPPED
=======
## Latest: Overnight #25 — Per-Source Scout Summary (DRAFT PR)

**Branch:** `cursor/overnight-25-per-source-summary-5296` → draft PR pending
    10|
**Problem:** After overnight #22–#24 (alert-cap default + speedyapply SWE INTERN_INTL + AI College sources), main already soft-fails per source in scout.py but operators cannot see which sources failed or returned 304 in a normal `scan --once` / health path. Scan observability gaps made overnight/cloud-scan failures invisible without reading logs.

**Fixed / shipped:**
- **Per-source breakdown in scan output**: After `scout_all`, CLI now shows compact per-source summary with name, job count (or 0), and status: `ok` / `not_modified` (304) / `error` (with error detail)
- **Aggregate counts**: Added `sources_ok`, `sources_not_modified`, `sources_failed` to `PipelineStats` and `RefreshStats`
- **Soft-fail preserved**: One bad source never aborts the rest (already true — kept working and added regression test)
- **Implementation**:
  - `pipeline.py`: New `SourceSummary` dataclass tracks per-source status/jobs/error
    20|  - `PipelineStats` and `RefreshStats`: Added `sources: list[SourceSummary]` and aggregate counts
  - `run_scan()` and `refresh_jobs()`: Populate source summaries for each result
  - `cli.py`: Display per-source breakdown in `cmd_scan()` and `cmd_refresh_jobs()`
- **Tests**: 8 new focused tests in `tests/test_per_source_summary.py` covering mixed ok/304/error sources, soft-fail preservation, and aggregate counts
- All 522 tests passing ✅

**Impact:**
- Operators can immediately see which sources failed, returned 304, or succeeded in scan output
- No need to grep logs to diagnose overnight scan issues
    30|- Aggregate counts provide quick health check (e.g., "4 ok, 2 not_modified, 1 failed")
- Soft-fail behavior proven with regression test (one bad source doesn't stop others)

**Status:** Draft PR ready for review. All tests green. HANDOFF updated.

## Latest prior: Overnight #21 — Transient Probe-Fail Defer (PR #38) — LANDED
>>>>>>> 95ef471 (Overnight #25: per-source scout summary in scan output)

**Branch:** `cursor/overnight-22-unlimited-alert-cap-dacc` → squash-merged to main (c6b3761)

**Problem:** With `JOBRADAR_MAX_ALERTS_PER_SCAN` defaulting to 15, alert #16+ still landed in SQLite but never hit Discord — easy to think listings were "lost." Standing product priority: notification speed; false positives OK; missed jobs not OK.

**Fixed / shipped:**
- **Default unlimited:** `JOBRADAR_MAX_ALERTS_PER_SCAN` now defaults to `0` (unlimited) instead of `15`
- **Code:** Updated `notify.py` `max_alerts_per_scan()` to default to "0" with proper docstring
- **Environment defaults:** Updated `.env.example` and `.github/workflows/cloud-scan.yml` to default to `0`
- **Optional cap preserved:** When explicitly set to a positive value, existing overnight #18–#20 behavior still works:
  - Priority-first then Fortune500 then Other ordering
  - Overflow jobs are `cap_deferred` (JSONL persisted, NOT marked `was_notified`) so later scans can alert them
- **Probe/pause defer:** Preserved overnight #21 `probe_deferred` and `alerts_paused` defer semantics
- **Tests:** Updated 3 tests to expect 0 as default; all 514 tests pass ✅
- **Documentation:** Updated `CLOUD_SCAN.md` and `LIVE_SCAN_VALIDATION.md` to reflect unlimited-by-default with optional cap

**Impact:**
- No more artificial per-scan alert ceiling by default — all qualifying jobs alert
- Users won't miss alert #16+ due to default cap
- Optional cap still available via env var for spam control if needed
- Deferred jobs (cap, pause, probe) can still retry on later scans

## Latest prior: Overnight #23 — Add speedyapply INTERN_INTL source (PR #41) — SHIPPED

**Branch:** `cursor/overnight-23-speedyapply-intl-9967` → squash-merged to main (f3a2dad)

**Goal:** Add the PROJECT_SPEC-planned speedyapply international internship source that was missing.

**Changes:**
- Added `speedyapply-swe-intl-2027` source pointing to `INTERN_INTL.md` (markdown parser)
- URL: `https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/INTERN_INTL.md`
- Uses same markdown parser as vansh/speedyapply README (handles pipe tables with ↳ inheritance)
- Tests: 3 new tests in `test_sources_policy.py`:
  - `test_speedyapply_intl_source_present`: Verifies INTERN_INTL source is in catalog
  - `test_newgrad_sources_disabled`: Confirms NEW_GRAD_INTL/USA sources remain disabled
  - Updated `test_sources_are_internship_focused` to include INTERN_INTL in allowed patterns
- Pittcsc ban tests intact (still excluded)
- Updated PROJECT_SPEC.md Sources section (removed "later" notation)
- New-grad sources (NEW_GRAD_INTL.md, NEW_GRAD_USA.md) remain disabled (Rohan targets internships only)

## Latest prior: Overnight #24 — speedyapply AI College Jobs Sources (PR #42)

**Branch:** `cursor/overnight-24-ai-sources-d634`

**Goal:** Complete final PROJECT_SPEC Sources item: add speedyapply AI sibling repo internship sources (README.md + INTERN_INTL.md only; exclude new-grad files).

**Implemented:**
- **Two new AI internship sources** in `src/jobradar/sources.py`:
  - `speedyapply-ai-2027` → `https://raw.githubusercontent.com/speedyapply/2027-AI-College-Jobs/main/README.md`
  - `speedyapply-ai-intl-2027` → `https://raw.githubusercontent.com/speedyapply/2027-AI-College-Jobs/main/INTERN_INTL.md`
- **Policy enforcement**: NEW_GRAD_USA.md and NEW_GRAD_INTL.md explicitly excluded (internship focus)
- **Tests** in `tests/test_sources_policy.py`:
  - `test_speedyapply_ai_sources_enabled()` — verifies both AI internship sources present
  - `test_speedyapply_ai_newgrad_banned()` — enforces new-grad exclusion policy
  - Updated `test_sources_are_internship_focused()` documentation to include AI sources
- **Documentation**:
  - `PROJECT_SPEC.md` updated: AI sibling repo listed with clear internship-only note
- Mirrors overnight #23 pattern for speedyapply-swe sources
- All sources remain internship-focused; pittcsc ban intact

**Testing:** Ready to merge (rebased onto PRs #40 and #41)


## Latest prior: Overnight #21 — Transient Probe-Fail Defer (PR #38) — LANDED
  - `cli.py`: Include `probe_deferred` in scan output
- **Tests**: 13 new tests in `tests/test_probe_defer.py`
- Rebased onto main after PR #39 merged (parser hardening + pause/cap defer)

**Impact:**
- Transient network issues no longer permanently silence jobs
- Jobs with temporary probe failures can be re-alerted on next successful scan
- Three deferral categories now tracked: `probe_deferred`, `alerts_paused`, `cap_deferred`
- All 514 tests passing ✅
- **Status:** Squash-merged to main (62e7e56) after clean rebase. No live Discord/ntfy/Telegram sends during merge.

## Latest prior: Fix failing pytest on main (PR #39)

**Problem:** Overnight PRs #27–#36 squash-merged to main resulted in ~9 pytest failures:
1. Parser hardening tests (PR #28) landed but actual parser changes lost during conflict resolution
2. Alert gates test expected old behavior where paused alerts permanently marked jobs as notified

**Fixed / shipped:**
- **Parser hardening restored (from PR #28 / commit d234dac):**
  - Import `is_bad_url` and validate URLs at parse time
  - Reject bad URLs (example.com, localhost, generic career pages) in `_clean_url()`
  - Improve URL inheritance for ↳ rows in HTML/markdown parsers
  - Skip orphan inherit markers (↳ with no previous company)
  - Add try/except for HTML parser robustness
  - All 31 parser hardening tests pass ✅

- **Alert pause/cap defer (from PR #37):**
  - Add `record_as_notified` parameter to `Notifier.notify()` (default `True`)
  - Add `alerts_paused` and `cap_deferred` counters to `PipelineStats`
  - When alerts paused: write JSONL but don't mark as notified → allows retry after re-enable
  - When cap hit: defer overflow jobs without marking notified → later scans can alert them
  - Quality blocks (bad URL, old posting) remain permanent
  - Preserve priority-first ordering from overnight #19
  - All 22 alert gates tests pass ✅

**Impact:**
- CI green, no more failure emails from GitHub Actions
- Parser quality: bad URLs rejected at parse time
- Safe pause: alerts can be paused without permanently silencing jobs
- Cap overflow recovery: jobs past cap can alert on later scans
- All 501 tests passing ✅

## Latest prior: Overnight #12 — Product-completion tests (PR #29)

**Problem:** After parser hardening (PRs #27, #28), needed comprehensive product-completion tests to validate the full scan → classify → store → notify pipeline with all quality gates.

**Fixed / shipped:**
- **10 new product-completion tests** in `tests/test_pipeline_quality_gates.py`
- **Bad URL blocking:** Tests that empty URLs, placeholders (TBD/N/A), generic career pages (`/careers`, `/jobs/search`), and probe failures are blocked from notifications
- **HTML sanitization:** Tests that HTML tags in company/title fields trigger block
- **Domain/company matching:** Tests that domain mismatches (e.g., Google job on facebook.com) are blocked
- **Recruiting platform allowlist:** Tests that Greenhouse, Lever, Ashby URLs pass domain check when company name in path
- **Alert cap enforcement:** Tests that `JOBRADAR_MAX_ALERTS_PER_SCAN` works correctly (notifies cap, rest marked silent)
- **Error resilience:** Tests that Director/Notion API errors don't crash the pipeline (try-except blocks working)
- **Posted_at window logic:** Tests both `JOBRADAR_REQUIRE_POSTED_AT=1` (strict) and `=0` (fallback to first_seen_at)
- **Full integration test:** Comprehensive test with mix of good/bad jobs through complete pipeline
- All 272 tests pass (262 existing + 10 new)

**Impact:**
- Product-completion coverage proves pipeline can run safely overnight without spamming bad URLs
- Quality gates validated: scan → classify → dedupe → store → notify gates all tested
- Error paths proven resilient (Director/Notion failures don't break alerting)
- Alert cap enforcement confirmed working

**Next:** Live scan validation docs (after product-completion tests ship)

## Latest prior: Job apps org + cloud scan (PR #17)

**Problem:** Duplicate flat vs nested Gmail labels; Notion hard to navigate; scan required Mac awake (`scan --loop`).

**Fixed / shipped:**
- Gmail sync uses **only** nested `JobRadar/*` labels; better company/role parsing (no more `myworkday` / `greenhouse mail` as company)
- Gmail→Notion creates/updates application rows even without a scout job match; sets Tier + Role family + Date applied
- Notion Tracker: Date applied property + views **Pipeline**, **Needs Action**, **Priority Active**, **By Tier**
- GitHub Actions **`cloud-scan`** every 30 min — laptop can stay closed (see `docs/CLOUD_SCAN.md`)

**Rohan one-time:** add Actions secrets (Discord/Notion/optional Gmail JSON) and run workflow once.

## Latest prior: Notion Backlog Flooding Fix + Internships-Only Filter (PR #15)

**Problem 1:** Pipeline was creating Notion Backlog pages for ALL new jobs, including those that failed quality gates (bad URLs, old postings, etc.). Rohan's Notion filled with thousands of non-actionable listings.

**Problem 2:** New-grad/full-time job listings were polluting internship alerts. Rohan targets summer/off-season internships for 2026–2027, not new-grad roles.

**Fixed:**
- `src/jobradar/pipeline.py`: Notion upsert now ONLY happens when `should_alert=True` (Discord-worthy jobs)
- Non-alert jobs (outside 14-day window, bad URLs, failed probes) skip Notion entirely
- Gmail-sourced status updates (Applied/OA/Interview) still work — separate path preserved
- `src/jobradar/models.py`: Added `posted_at` field to JobRecord for company/source post dates
- `src/jobradar/notion.py`: Notion `Posted` property now populated when `posted_at` is available (not faked with first_seen)
- `src/jobradar/sources.py`: Disabled `simplify-newgrad` source by default (New-Grad-Positions repo no longer scraped)
- `src/jobradar/classify.py`: New-grad/full-time roles filtered unless also clearly internships
  - Added NEWGRAD_SIGNALS: "new grad", "full-time", "entry level", etc.
  - Added INTERN_SIGNALS: "intern", "co-op", "summer", etc.
  - Exclude new-grad-only titles, keep true intern roles
- Tests:
  - `test_pipeline_no_notion_for_non_alert_jobs`: Verifies no Backlog dumps for silent jobs
  - `test_notion_posted_date_wiring`: Verifies Posted property populated when date available
  - `test_exclude_newgrad_fulltime`: Verifies new-grad filtering (exclude new-grad, keep interns)
- All 212 tests pass

**Impact:** 
- Notion only receives meaningful internship jobs that pass Discord quality gates
- Backlog status reserved for human/Gmail moves, not scout dumps
- New-grad/full-time roles filtered out; summer/off-season internship sources prioritized
- Posted dates visible in Notion when parsers provide them

## What works now (MVP)

Python scout → parse → classify → dedupe → SQLite → mock notify JSONL.

```bash
cd "/Users/rohankilaru/Resume Bot/job-agent-notifier"
source .venv/bin/activate   # or: python3 -m venv .venv && pip install -e ".[dev]"
pytest
python -m jobradar health
python -m jobradar scan --once
python -m jobradar ping-grok
python -m jobradar verify-links --help
```

- Alerts: `data/notifications.jsonl` (gitignored)
- DB: `data/jobradar.db`
- Empty Grok/Twilio/Discord/Gmail keys → skip; never blocks notify
- Parent Resume Bot gitignores this tree; this folder has its own git remote

## Grok Bots (Grok Bot app)

Created: JobRadar Director, Analyst, Resume Mapper, Strategist, Inbox, Weekly.  
Group chat: **JobRadar** (all six).

**Wake path (adapted):** Director webhook only if UI exposes URL/key.  
Specialist per-bot webhook credential UI may be unavailable — Director fans out via in-app messaging instead of five webhook URLs.  
Director routine: `jobradar-director` (webhook).

## Discord Multi-Tier Routing (NEW)

**Feature:** Discord alerts now route to different channels based on company tier:
- **Priority** — Strategic high-value employers (OpenAI, Anthropic, Databricks, Snowflake, Nvidia, Scale AI, Perplexity, Meta, Google, Microsoft, Apple, Tesla, Palantir, Stripe, Figma, Roblox, Netflix, Jane Street, Hudson River Trading, Citadel, Ramp, Cursor, Anduril, xAI)
- **Fortune500** — Large established employers not in Priority (banks, industrials, big tech adjacent). Maintainable list in `src/jobradar/tier.py`
- **Other** — Everything else that passes alert gates

**Setup:**
1. Create 3 Discord channels (e.g., `#jobradar-priority`, `#jobradar-fortune500`, `#jobradar-other`)
2. For each channel: Settings → Integrations → Webhooks → copy URL
3. Set env vars in `.env`:
   - `DISCORD_WEBHOOK_PRIORITY=https://discord.com/api/webhooks/...`
   - `DISCORD_WEBHOOK_FORTUNE500=https://discord.com/api/webhooks/...`
   - `DISCORD_WEBHOOK_OTHER=https://discord.com/api/webhooks/...`
4. Legacy `DISCORD_WEBHOOK_URL` is fallback for any tier without specific URL

**Implementation:**
- Tier classification: `src/jobradar/tier.py` (fuzzy company name matching)
- Webhook routing: `src/jobradar/notify.py` (`get_discord_webhook_url`, `send_discord`)
- Tests: `tests/test_tier_routing.py` (22 tests, full coverage)
- Fallback chain: tier URL → legacy URL → skip Discord

## Overnight #9 Delivered (verify-links + probe gate)

**PR #10:** `cursor/overnight-9-verify-links-probe-e4c7`

- `verify-links` CLI (`python -m jobradar verify-links`) probes job URLs from SQLite or provided list
- Prints summary: checked/good/bad/error counts
- Optional `--mark-bad` silently marks failed URLs as closed (no Discord/ntfy/Telegram/Notion/Grok)
- Notify path wired: Discord/ntfy/Telegram fire ONLY when URL has probed-good proof
- Respects `JOBRADAR_LINK_PROBE` env var (default 1 for real notifies; tests set 0)
- Empty/placeholder URLs (TBD, N/A, null, etc.) never alert
- Probe failures → silent (Notion Backlog / skip alert), never block pipeline
- New module: `src/jobradar/link_probe.py`
- Tests: `tests/test_link_probe.py` (14 new tests, full pytest green)

Usage:
```bash
python -m jobradar verify-links --help
python -m jobradar verify-links --priority-only --verbose
python -m jobradar verify-links --mark-bad
python -m jobradar verify-links --urls https://example.com/job1 https://example.com/job2
```

## Overnight #8 — Skip empty/bad URLs + silent quarantine (DELIVERED)

**Issue:** Production alerts (Discord/ntfy/Telegram) received empty or placeholder URLs (example.com, localhost, etc.) from parser/DB rows.

**Fixed:**
- **Ingest filter:** Pipeline now skips jobs with empty/placeholder URLs before upsert/notify. No Discord/ntfy/Telegram/Grok for bad URLs.
- **Quarantine CLI:** `python -m jobradar quarantine-bad-urls` scans existing SQLite jobs and marks bad URLs as closed (silent, no alerts, no Notion, no Grok).
  - Optional probe: set `JOBRADAR_LINK_PROBE=1` to HEAD-probe URLs (default off).
  - Tests mock HTTP; production can enable probe after testing.
- **Tests:** Full pytest coverage for URL validation, ingest skip, and quarantine paths.

**Remaining work (Rohan-only):**
- Director webhook key wiring (Grok Bot app UI may not expose per-specialist keys yet)
- No new Gmail work; inbox bot is Phase 4

## Next (MVP → production)

**Delivered in open overnight PRs #1–#5:**
- 14-day notify (backfill older into DB silently) — PR #1
- Parser hardening (↳, Inactive, column alignment) — PR #1
- Product completion tests — PR #2
- Link verification gate + parser column alignment — PR #3
- Live scan validation docs + harness — PR #4
- Classify exclude-list tuning — PR #5 (partial)
- ping-grok / Director empty-key hardening + safe DB refresh — PR #5 (this PR)

- Silent job refresh CLI (`refresh-jobs`) — PR #8

**Remaining (not yet merged):**
1. Director `.env` keys wiring (by Rohan after specialist UI exposes webhook URLs)
2. Twilio SMS deferred (ntfy is the phone push path)
3. Draft PR #23: Gmail/Notion inbox pack (do NOT touch — separate workstream)
4. Do **not** scrape `pittcsc/Summer2027-Internships`

## Rohan-only items (blocked on keys/credentials)

- Director keys (Grok Bot webhook URLs) — requires Grok Bot UI credential access
- Gmail setup (Phase 4) — `secrets/gmail-client.json` OAuth flow
- Actions Discord/Notion secrets (cloud-scan workflow)

## Key modules

- `src/jobradar/parsers.py` — JSON + Simplify HTML (`↳`, Inactive)
- `src/jobradar/scout.py` — ETag cache; `sources=[]` means no sources (not all)
- `src/jobradar/pipeline.py` — end-to-end
- `src/jobradar/grok.py` — optional webhooks, 8s timeout
- `src/jobradar/link_probe.py` — URL health probing (overnight #9)
- `src/jobradar/notify.py` — JSONL + Discord/ntfy/Telegram with probe gate
- Specs: `agents/grok/*.spec.md`

## Standing rules

Priority: notification speed. False positives OK. Missed jobs not OK.  
No auto-apply. No email alerts.
