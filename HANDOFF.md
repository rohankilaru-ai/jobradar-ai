# JobRadar-AI — Handoff for Cursor (post-MVP)

**Repo:** https://github.com/rohankilaru-ai/jobradar-ai  
**Local:** `/Users/rohankilaru/Resume Bot/job-agent-notifier/`  
**Branch:** `main`

## Latest: Overnight #20 — Pause/Cap Defer Without Permanent Notify Silence

**Problem:** When alerts are paused (`JOBRADAR_ALERTS_ENABLED=0`) or alert cap is hit (`JOBRADAR_MAX_ALERTS_PER_SCAN`), jobs were silently marked as notified in the database. This permanently silenced them - they would never get live Discord/ntfy/Telegram alerts even after:
- Alerts were re-enabled
- Cap was raised or later scans had spare capacity

**Fixed / shipped (PR #TBD):**
- **Pause defer:** When `JOBRADAR_ALERTS_ENABLED=0`, jobs write JSONL but do NOT record notification in DB. After re-enable, these jobs remain eligible for live alerts on a subsequent scan (if still new and within window).
- **Cap defer:** When `JOBRADAR_MAX_ALERTS_PER_SCAN` overflow, jobs beyond the cap write JSONL but do NOT record notification. Later scans can alert previously deferred jobs (subject to window/cap/quality gates).
- **Live alerts:** Jobs that receive actual Discord/ntfy/Telegram alerts are marked notified (prevents double-alert).
- **Quality blocks:** Jobs failing quality gates (bad URL, example.com, outside window) still block as before; these are permanent blocks, not deferrals.
- **Stats counters:** Added `alerts_paused` and `cap_deferred` to `PipelineStats` for clear logging.
- **Tests:** 11 comprehensive tests (`tests/test_pause_cap_defer.py`) prove defer behavior; all 273 tests pass.

**Implementation:** `Notifier.notify()` gained `record_as_notified` parameter (default True). Pipeline detects pause/cap conditions and sets `record_as_notified=False` for deferred jobs. Quality gates remain unchanged.

**Impact:** Alerts can be safely paused for maintenance without losing jobs. Alert cap overflow no longer permanently silences Priority jobs that lost slots before overnight #19's ordering lands. All 273 tests green.

## Latest prior: Job apps org + cloud scan (this PR)

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
2. Optional: Twilio SMS + Discord webhook fine-tuning
3. Later: Gmail inbox bot (Phase 4), 24/7 VM for Python loop
4. Do **not** scrape `pittcsc/Summer2027-Internships`

## Rohan-only items (blocked on keys/credentials)

- Director keys (Grok Bot webhook URLs) — requires Grok Bot UI credential access
- Gmail setup (Phase 4) — `secrets/gmail-client.json` OAuth flow

## Open overnight draft stack (do NOT merge or rebase without Rohan)

Drafts #27–#36 (and possibly older #22/#23) remain open and unmerged. Draft PR #TBD (overnight #20, pause/cap defer) is self-contained against current main and does not depend on the stack.

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
