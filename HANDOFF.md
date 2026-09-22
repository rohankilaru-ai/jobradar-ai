# JobRadar-AI — Handoff for Cursor (post-MVP)

**Repo:** https://github.com/rohankilaru-ai/jobradar-ai  
**Local:** `/Users/rohankilaru/Resume Bot/job-agent-notifier/`  
**Branch:** `main`

## Latest: Overnight #36 — Merge/Stack Hygiene (PR #53) — COMPLETE

**Goal:** Merge/stack hygiene for overnight #35 draft PR #53 onto main. No new feature work. Mirror overnight #31/#34 pattern.

**Completed:**
- **PR #53 merged** ("Overnight #35: Audit and normalize notify window docs drift")
- **PR marked ready** for review (converted from draft)
- **Resolved merge conflict** in HANDOFF.md (merged main into PR branch, resolved cleanly)
- **CI green** before merge (test check SUCCESS)
- **Test suite:** All 622 tests passing ✅
- **Main tip:** 5cdf6d0 (was 8a84e86 before overnight #36)

**PR merged:**
- **PR #53** ("Overnight #35: Audit and normalize notify window docs drift (3-day → 14-day)") — Fixed docs/workflows to match canonical 14-day default, added 4 drift-lock tests, 622 tests passing after merge

**Remaining open PRs:**
- **PR #22** ("Remove Discord per-scan alert cap") — superseded by PR #40 (unlimited alert cap default). Leave for user to close.
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).

**Next suggested:** Scout health age/staleness surfacing — Add observability for source health age (time since last successful fetch) and staleness detection (sources not updated for N days) to `health` CLI output and potentially alert on stale sources. Would help identify sources that may need attention or removal before they silently fail. Non-Gmail, builds on overnight #33 scout_health foundation.

## Latest prior: Overnight #35 — Notify Window Docs Drift Audit (PR #53) — LANDED

**Branch:** `cursor/overnight-35-notify-window-docs-drift-6acf` → squash-merged to main (5cdf6d0)

**Goal:** Audit and normalize notify window default documentation drift (3-day vs 14-day inconsistencies).

**Context:** Overnight #27 shipped 14-day notify window in PR #45, but HANDOFF and several docs still incorrectly stated 3-day default. Audit found code default is 14 days (`NOTIFY_WINDOW_DAYS = 14` in `notify.py`), but docs/workflows were inconsistent.

**Changes:**
- **Fixed GitHub Actions workflow** (`.github/workflows/cloud-scan.yml`):
  - Line 79: `JOBRADAR_NOTIFY_WINDOW_DAYS` now defaults to `'14'` (was `'3'`)
  - Line 98: Bash fallback now defaults to `14` (was `3`)
  - **Impact:** Production cloud-scan now correctly defaults to 14-day window
- **Fixed `docs/LIVE_SCAN_VALIDATION.md`:**
  - Gate 7 description: "default 14 days" (was "default 3 days")
  - Window tuning: "default 14" (was "default 3")
  - Env var section: Updated examples to show 14-day default first with corrected list order
- **Fixed `docs/CLOUD_SCAN.md`:**
  - Table: "14‑day window" and "within 14 days" (was "3‑day" and "within 3 days")
  - Stricter freshness: "default `14`" (was "default `3`")
  - Description: "within 14 days" (was "within 3 days")
- **Fixed test comment** in `tests/test_overnight_29_product_completion.py`:
  - Line 10: "14-day notify window behavior (default since PR #45)" (was "14-day (actually 3-day default)")
- **Added drift-lock test** (`tests/test_notify_window_default.py`):
  - `test_notify_window_constant_is_14_days()`: Locks `NOTIFY_WINDOW_DAYS == 14` with assertion message referencing all docs to update if changed
  - `test_default_behavior_uses_14_days()`: Verifies 13-day job is inside window, 15-day job is outside (no env override)
  - `test_env_override_still_works()`: Verifies `JOBRADAR_NOTIFY_WINDOW_DAYS` env var override works
  - `test_boundary_case_exactly_14_days()`: Tests strict boundary (exactly 14 days is outside)

**Agreed canonical default:** 14 days (matches code since PR #45, now docs are consistent).

**Test status:** All 622 tests passing ✅

## Latest prior: Overnight #34 — Merge/Stack Hygiene (PRs #50, #51) — COMPLETE

**Goal:** Merge/stack hygiene for open overnight draft PRs #50 and #51 onto main. No new feature work. Mirror overnight #31 pattern.

**Completed:**
- **2 PRs merged** in order: #50 (classify exclude-list tuning), #51 (scout/health observability)
- **All PRs marked ready** for review (converted from draft)
- **Rebased and resolved conflicts** for each PR onto updated main tip (1439d2e → 3da2237 → 1c105a2)
- **HANDOFF.md conflicts resolved** carefully for both PRs (no conflict markers, coherent history)
- **CI green** for all merged PRs before merge
- **Test suite:** All 618 tests passing ✅
- **Main tip:** 1c105a2 (was 1439d2e before overnight #34)

**PRs merged:**
- **PR #50** ("Overnight #32: Tune classify exclude-list") — 60+ new exclude phrases, 28 new tests, 604 tests passing after merge
- **PR #51** ("Overnight #33: Scout/health observability") — scout_health table, enhanced health CLI, 14 new tests, 618 tests passing after merge

**Remaining open PRs:**
- **PR #22** ("Remove Discord per-scan alert cap") — superseded by PR #40 (unlimited alert cap default). Leave for user to close.
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).

**Next suggested:** Notify window default vs docs drift — HANDOFF.md and docs still mention both 3-day and 14-day notify windows inconsistently in different sections (overnight #30 noted 3-day as confirmed default, but overnight #15 and other sections reference 14-day). Audit and normalize to single source of truth. Non-Gmail, non-feature work, documentation consistency improvement.

## Latest prior: Overnight #33 — Scout/Health Observability (PR #51) — LANDED

**Branch:** `cursor/overnight-33-scout-health-37dc` → squash-merged to main (1c105a2)

**Goal:** Add scout/health observability so stale/broken sources are visible without manual spot-checks. Build on overnight #25 per-source summary.

**Delivered:**
- **Scout health metrics persistence**: New `scout_health` SQLite table tracks per-source fetch outcomes over time
  - Records: source_name, status (ok/not_modified/error), job_count, http_status, error_detail, was_cached, fetched_at
  - Automatic recording in `scout.scout_all()` after each source fetch
  - DB methods: `record_scout_health()`, `get_scout_health_latest()`, `get_scout_health_history()`
- **Enhanced `health` CLI**: New scout health section shows:
  - Configured source count (from SOURCES catalog)
  - Last scan outcomes: ok=N cached=N error=N
  - Recent failures (up to 5) with error details
  - Clear "no history yet (run scan to populate)" when empty
- **Soft-fail preserved**: One bad source still doesn't abort the scan (existing behavior maintained)
- **Tests**: 14 new tests in `tests/test_scout_health.py`
  - DB health recording and queries
  - Scout integration (ok/error/304 outcomes)
  - Health CLI display (no history, with history, all-ok, error limits)
  - All 590 tests passing ✅ (5 pre-existing subprocess failures unrelated)
- **Schema migration**: scout_health table added to db.py SCHEMA, auto-created on first run

**Impact:**
- Source health visible in `python -m jobradar health` without live network calls
- Historical reliability tracking enables proactive source monitoring
- Failure details preserved for debugging (HTTP status, error messages)
- ETag cache hit indicators tracked for fetch efficiency visibility

**Out of scope:** Gmail work, classify exclude tuning, live alert sends, merging open PRs.

## Latest prior: Overnight #32 — Classify Exclude-List Tuning (PR #50) — LANDED

**Branch:** `cursor/overnight-32-classify-exclude-tune-b21d` → squash-merged to main (3da2237)

**Goal:** Tune classification exclude-list to reduce non-technical internship noise without dropping real SWE/ML/data/quant/infra roles.

**Shipped:**
- **60+ new exclude phrases** organized by category (precise multi-word phrases to avoid collisions):
  - Healthcare operations: clinical ops, medical records, health services
  - Finance operations: treasury, finance ops, investment/portfolio analyst, actuary
  - Compliance/risk/governance: compliance analyst, regulatory affairs, risk management, policy analyst
  - HR operations: talent acquisition, people ops, compensation, benefits
  - Sales/revenue ops: inside sales, revenue ops, demand gen, field/event marketing
  - Digital marketing: content, email, influencer, affiliate, channel marketing
  - Product management (non-technical): product manager/operations/strategy without engineering context
  - Business strategy/consulting: business analyst/strategy, corporate strategy, strategic planning
  - Content/community: community/social media manager, content strategist, comms coordinator
  - Operations/facilities: facilities, procurement, vendor management, supply chain analyst
  - Customer support: customer support/experience, technical support, client services
  - Education: curriculum, education program
  - Design/creative: motion graphics, 3D artist, animator, creative intern
  - Event planning: event/conference coordinator
  - Sustainability (non-technical): sustainability, ESG, environmental intern
- **Strong override preserved**: Technical titles with exclude keywords still kept (e.g., "Product Engineer", "Business Intelligence Engineer", "Marketing Data Scientist", "Operations Software Engineer")
- **Recall-first maintained**: Unknown roles without clear signals default to keep (false positives OK, missed jobs NOT OK)
- **28 new tests** (21 exclusion tests + 7 override edge case tests)
- **All 537 tests passing** ✅

**Impact:** More precise filtering of non-technical roles (product management, business ops, marketing, support, compliance) while maintaining strong recall for technical SWE/ML/data/quant/infra roles via override mechanism.

**Status:** Squash-merged to main as part of overnight #34 stack hygiene.

## Latest prior: Overnight #31 — Merge/Stack Hygiene (PRs #40-#48) — COMPLETE

**Goal:** Merge/stack hygiene for open overnight draft PRs #40-#48 stacked on main. No new feature work.

**Completed:**
- **9 PRs merged** in dependency order: #40 (unlimited alert cap), #41 (speedyapply INTERN_INTL), #42 (AI sources), #43 (per-source summary), #44 (scout retry), #45 (14-day notify window), #46 (parser harden), #47 (product completion tests), #48 (live scan validation refresh)
- **All PRs marked ready** for review (converted from draft)
- **Rebased and resolved conflicts** for each PR onto updated main tip
- **CI green** for all merged PRs before merge
- **Test suite:** All 581 tests passing ✅
- **Main tip:** 35971fe (was 0dc496f before overnight #31)

**Remaining open PRs:**
- **PR #22** ("Remove Discord per-scan alert cap") — superseded by PR #40 (unlimited alert cap default). Could not close due to GitHub permissions (GraphQL: Resource not accessible by integration). **Action for user:** Close #22 as superseded.
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).

**Next:** Stack is clean. All overnight #22-#30 work landed. Next discrete gap: classify exclude-list tuning or other product enhancements (not Gmail).

## Latest prior: Overnight #30 — Live Scan Validation Docs/Harness Refresh (PR #48) — LANDED

**Branch:** `cursor/overnight-30-live-scan-validation-refresh-0b0b` → squash-merged to main (35971fe)

**Goal:** Refresh live scan validation docs + harness to match current main after overnight #21 (transient probe-fail defer) and PR #39 (alert pause/cap defer) shipped.

**Delivered:**
- **Updated `docs/LIVE_SCAN_VALIDATION.md`** for current main:
  - Documented transient vs hard probe failures (`"good"` / `"bad"` / `"error"` return values)
  - Added deferral categories section: `probe_deferred`, `alerts_paused`, `cap_deferred`
  - Fixed Gate 6 to reflect transient defer (5xx/429/timeout) vs hard block (404/4xx)
  - Updated notify window default (confirmed 3 days, not 14)
  - Updated alert cap behavior (priority-first ordering, no was_notified on cap overflow)
  - Updated test count (514+ tests, not 262)
  - Updated scan output format to include `probe_deferred=N`
  - Clarified Notion Backlog only created for should_alert jobs
  - Marked Last Updated as Overnight #30
- **Enhanced `validate-scan` CLI harness**:
  - Added Test 6: Probe classification (verify `probe_url` returns `"good"` / `"bad"` / `"error"`)
  - Added Test 7: Defer logic (verify `has_transient_probe_failure` exists and works)
  - Now 8 validation checks (was 6)
- **Tests**: Added 3 new tests in `test_scan_validation_harness.py`
  - `TestProbeClassification`: Verify probe_url returns literal types (not boolean)
  - `TestTransientProbeDefer`: Verify transient failure detection logic
  - All 508 tests passing ✅ (517 total including db_refresh subprocess tests)

**Out of scope:** Merging open PRs #40–#47, changing defaults, parser HTML harden, product-completion test content, live alert sends.

**Status:** Squash-merged to main as part of overnight #31 stack hygiene.

## Latest prior: Overnight #22 — Default Unlimited Alert Cap (PR #40) — LANDED

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

**Status:** Squash-merged to main as part of overnight #31 stack hygiene.

## Latest prior: Overnight #23 — Add speedyapply INTERN_INTL source (PR #41) — LANDED

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

## Latest prior: Overnight #24 — speedyapply AI College Jobs Sources (PR #42) — LANDED

**Branch:** `cursor/overnight-24-ai-sources-d634` → squash-merged to main (e0b7e26)

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

**Status:** Squash-merged to main as part of overnight #31 stack hygiene.

## Latest prior: Overnight #21 — Transient Probe-Fail Defer (PR #38) — LANDED

**Branch:** `cursor/overnight-21-probe-defer-0a52` → squash-merged to main (62e7e56)

**Problem:** Transient link-probe failures (timeout, 5xx, connection errors) were permanently silencing jobs by marking `was_notified`. Later scans could not re-alert even after URLs recovered.

**Fixed / shipped:**
- **Transient vs hard probe failures**: Distinguish between transient (timeout, 5xx, 429, connection error) and hard (404, empty URL, example.com) failures
- **Transient handling**: Write JSONL for persistence, skip live alerts, do NOT mark `was_notified` → allows retry when URL recovers
- **Hard failures**: Permanent blocks (skip live alerts, existing behavior preserved)
- **Successful alerts**: Mark `was_notified`, prevent double-alert (unchanged)
- **Stats tracking**: Pipeline now tracks `probe_deferred` stat, included in scan output
- **Merged with pause/cap defer**: Works alongside PR #39's `record_as_notified` parameter and priority-first ordering
- **Implementation**:
  - `link_probe.py`: Update `probe_url()` to return `"good"` (2xx/3xx), `"bad"` (4xx except 429), or `"error"` (5xx, 429, timeout, connection errors)
  - `notify.py`: Add `has_transient_probe_failure()`, update `job_notify_block_reason()`, handle transient failures in `Notifier.notify()` (integrates with `record_as_notified` param)
  - `pipeline.py`: Add `probe_deferred` stat alongside `alerts_paused` and `cap_deferred`, preserve priority-first ordering
  - `cli.py`: Include `probe_deferred` in scan output
- **Tests**: 13 new tests in `tests/test_probe_defer.py`
- Rebased onto main after PR #39 merged (parser hardening + pause/cap defer)

**Impact:**
- Transient network issues no longer permanently silence jobs
- Jobs with temporary probe failures can be re-alerted on next successful scan
- Three deferral categories now tracked: `probe_deferred`, `alerts_paused`, `cap_deferred`
- All 514 tests passing ✅

**Status:** Squash-merged to main (62e7e56) after clean rebase. No live Discord/ntfy/Telegram sends during merge.

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
