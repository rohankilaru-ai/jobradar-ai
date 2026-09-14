# JobRadar-AI — Handoff for Cursor (post-MVP)

**Repo:** https://github.com/rohankilaru-ai/jobradar-ai  
**Local:** `/Users/rohankilaru/Resume Bot/job-agent-notifier/`  
**Branch:** `main`

## Latest: Notion Backlog Flooding Fix + Internships-Only Filter (PR #15)

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
