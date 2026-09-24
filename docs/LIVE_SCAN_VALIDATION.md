# Live Scan Validation Guide

This guide walks you through validating a live `scan --once` without guessing. Use this after initial setup, when tuning classification rules, or when verifying production readiness.

**Last Updated:** Sep 2026 (Overnight #43) — Cleaned conflict markers; refreshed for overnight #41 fixture/dummy URL gates, probe defer vs hard fail, 14-day notify window, classification recall (#39 TAM/TPM), scout health staleness (#37), and accurate `validate-scan` harness docs.

## Prerequisites

1. Python 3.11+ with venv
2. `.env` file exists (copy from `.env.example` if missing)
3. No secrets required for basic validation; Discord/ntfy/Telegram optional for end-to-end testing
4. `JOBRADAR_LINK_PROBE=0` in tests (default); `=1` for live probe validation

## Quick Validation Sequence

### 1. Environment Setup

```bash
cd "/Users/rohankilaru/Resume Bot/job-agent-notifier"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Run Tests (offline validation)

```bash
pytest -v
```

All tests should pass (**691+** on main tip after overnight #41; overnight #42/#43 add more). This validates:
- Classification rules (include/exclude keywords, #39 TAM/TPM strong-signal recall)
- Dedupe logic
- Database operations
- CLI command registration (including `validate-scan`)
- Notification logic (mocked, no live Discord)
- Link probe and quality gates
- Fixture/dummy URL gates (`is_fixture_or_dummy_url`, overnight #41)
- URL validation (empty URLs, generic career pages, domain mismatch)
- Notify window (posted_at vs first_seen_at; canonical **14-day** default)
- Scout health age/staleness (#37)

### 3. Comprehensive Validation Harness

```bash
python -m jobradar validate-scan
```

End-to-end **offline** validation of scan health **without** live notifications or a network scan.

This command covers:
- Health check (adapters configured or gracefully skipped)
- Classification smoke test (known good/bad jobs + TAM/TPM recall)
- Placeholder / specificity gates (empty URLs, generic career pages)
- **Fixture/dummy URL gates** (`is_fixture_or_dummy_url` → notify block *before* domain-match; probe short-circuit; expanded hosts; suffix-safe so `contest.com` ≠ `test.com`)
- Quality gate test (domain mismatch, HTML in company/title)
- Notify window test (posted_at vs first_seen_at; 14-day default; `REQUIRE_POSTED_AT=1`)
- Probe classification (empty/placeholder/fixture → `"bad"` hard fail)
- Defer logic smoke (`has_transient_probe_failure` with probe disabled → False)
- Database operations (upsert idempotence, dedupe)

**Does not:** fire Discord/ntfy/Telegram, call live Grok, or run `scan --once`.

**Output format (representative):**
```
JobRadar Scan Validation
==================================================

✓ Environment health check passed
✓ Classification logic validated (5/5 tests passed)
✓ Link probe gates validated (5/5 tests passed)
✓ Fixture/dummy URL gates validated (10/10 tests passed)
✓ Quality gates validated (4/4 tests passed)
✓ Notify window logic validated (3/3 tests passed; default=14d)
✓ Probe classification validated (3/3 tests passed)
✓ Defer logic validated (1/1 tests passed)
✓ Database operations validated (2/2 tests passed)

All validation checks passed! ✨
```

If any check fails, the output shows which validation failed and why. The harness saves/restores `JOBRADAR_LINK_PROBE` so it does not permanently mutate process env.

### 4. Health Check

```bash
python -m jobradar health
```

Expected output (shape; counts vary):
```
jobradar 0.1.0 ok
db: data/jobradar.db (N jobs, M applications)
notifiers: jsonl [+ discord] [+ ntfy] [+ telegram]
alerts: enabled (unlimited, require_posted_at)
notion: configured | skipped until keys set
gmail: skipped until secrets/gmail-client.json
grok webhooks: configured | skipped until keys set
director: configured | skipped until keys set

Runtime gates:
  notify window: 14 days
  link probe: enabled
  alerts: enabled
  require posted_at: yes
  max alerts/scan: unlimited

Scout health:
  configured sources: N
  staleness threshold: 3 days
  last scan: ok=… cached=… error=…
  Age/staleness summary:
    fresh: … (updated within 3 days)
    stale: … (not updated for >3 days)
```

**Scout health (#37):** `health` surfaces source age and staleness (default threshold 3 days). Stale / never-fetched sources are listed so quiet adapters are visible without a manual spot-check.

**Fast path guarantee**: Missing keys → skip gracefully. Never blocks alerts.

### 5. Dry-Run Scan (no notifications)

```bash
JOBRADAR_ALERTS_ENABLED=0 python -m jobradar scan --once
```

**Use `JOBRADAR_ALERTS_ENABLED=0` for safe testing:**
- Fetches and processes sources normally
- Writes to SQLite as usual
- Writes `data/notifications.jsonl`
- **Skips Discord/ntfy/Telegram** (never fires live webhooks)
- **Skips Notion upsert** (only creates Backlog pages for jobs passing should_alert gates)
- **Does NOT mark was_notified** (allows retry after re-enable)
- Grok webhooks still fire if configured (to test Director)

**First run** (empty DB):
```
first scan seeded=N jobs (no alerts). next scan will notify only new listings.
scan done fetched=X kept=Y new=N notified=0 alerted=0 probe_deferred=0
```

**Subsequent runs** (includes per-source breakdown **and** probe defer count):
```
scan done fetched=X kept=Y new=Z notified=Z alerted=0 probe_deferred=0
sources: ok=4 not_modified=2 failed=0
  aprameyak-2027: 15 jobs
  dreamwork-2027: not_modified (304)
  applyguy-2027: 8 jobs
  simplify-summer-2027: 23 jobs
  simplify-offseason-2027: not_modified (304)
  vansh-summer-2027: 12 jobs
```

**With deferrals** (alerts paused, cap hit, or transient probe failures):
```
scan done fetched=X kept=Y new=Z notified=W alerted=0 probe_deferred=P
alert_cap_hit: more new jobs existed but JOBRADAR_MAX_ALERTS_PER_SCAN stopped further Discord/ntfy this run
```

Where `probe_deferred=P` shows jobs with transient probe failures (timeout/5xx/429) that will retry next scan.

Where:
- `fetched` = total job listings parsed from all sources
- `kept` = listings passing classification (not excluded)
- `new` = listings not seen before
- `notified` = new listings written to JSONL
- `alerted` = new listings sent to Discord/ntfy/Telegram (0 when JOBRADAR_ALERTS_ENABLED=0)
- `probe_deferred` = new listings with transient probe failures (timeout/5xx/429), deferred without marking was_notified
- `sources` = per-source breakdown showing which sources succeeded (ok), returned 304 (not_modified), or failed (error)

### 6. Live Scan (with notifications)

```bash
python -m jobradar scan --once
```

**Only run this when you're ready for live Discord/ntfy/Telegram notifications!**

### 7. Link Verification

```bash
python -m jobradar verify-links
```

Validates URLs from SQLite. Check for:
- No `example.com` / fixture hosts or empty URLs leak through
- Company/URL domain mismatch caught
- Only probed-good URLs reach notifications

**Options:**
- `--priority-only` — Check only priority company jobs
- `--limit N` — Check only first N jobs
- `--urls URL1 URL2 ...` — Check specific URLs instead of DB
- `--mark-bad` — Mark failed URLs as closed (silent, no Discord)
- `--verbose` — Print each URL result

## Quality Gates (Main/Current)

JobRadar implements multiple layers of quality gates to ensure only valid, actionable job postings reach Discord/ntfy/Telegram. These gates are enforced in `notify.py::job_notify_block_reason()`.

### Gate 1: HTML Tag Detection

**Block:** Jobs with HTML tags in company or title fields.

**Why:** Indicates parser failure or malformed data.

**Examples:**
- Company: `<div>Stripe</div>`
- Title: `Software Engineer<br>Intern`

**Handled:** Parser strips HTML; if it leaks through, blocked at notify.

### Gate 2: Empty or Placeholder URLs

**Block:** Jobs with empty, null, or placeholder URLs.

**Why:** Cannot apply to a job without a valid application link.

**Examples:**
- Empty string, `""`
- `"TBD"`, `"N/A"`, `"null"`, `"undefined"`
- Missing `http://` or `https://` scheme

**Handled:** `is_placeholder_url()` / empty sanitize → blocked.

### Gate 3: Fixture / Dummy / Local URLs (Overnight #41)

**Block:** Jobs with test fixture, dummy, or local hosts — **before** domain-match / specificity checks.

**Why:** Test data and placeholder hosts must never reach production notifications, even when the company name loosely matches the host (e.g. company=`Test` + `test.com`, company=`Example` + `example.net`).

**Shared helper:** `is_fixture_or_dummy_url()` in `models.py` (suffix-safe so `contest.com` ≠ `test.com`).

**Expanded bad hosts include:**
- `example.com`, `example.org`, `example.net`
- `test.com`, `test.org`
- `localhost`, `127.0.0.1`, `0.0.0.0`
- `about:blank`, `placeholder.com`

**Notify path:** `job_notify_block_reason` returns `fixture/dummy URL: …` **before** domain-match / generic-career checks.

**Probe path:** `probe_url` **short-circuits** fixture hosts locally (no HTTP) → `"bad"`. (Some fixture hosts like `example.com` can return HTTP 200.)

**Ingest path:** Parser still strips fixtures via `is_bad_url` → empty URL.

### Gate 4: Generic Career Pages (Not Specific Job Postings)

**Block:** URLs pointing to general career homepages or search pages, not specific job postings.

**Why:** Generic `/careers` or `/jobs` pages are not actionable — users need a direct application link.

**Examples (Blocked):**
- `https://stripe.com/careers`
- `https://meta.com/jobs`
- `https://greenhouse.io/jobs/results`

**Examples (Allowed):**
- `https://stripe.com/careers/job/1234` — specific job ID
- `https://boards.greenhouse.io/stripe/jobs/1234?gh_jid=1234` — Greenhouse job
- `https://jobs.lever.co/stripe/uuid` — Lever job

**Handled:** `is_specific_job_url()` analyzes path and query parameters.

**ATS Platforms Recognized:**
- Greenhouse (`greenhouse.io`, `gh_jid=`)
- Lever (`lever.co`)
- Ashby (`ashbyhq.com`)
- Workday (`myworkday.com`, `/job/`)
- iCIMS (`icims.com`, `/job`)
- Taleo (`taleo.net`, `/jobdetail`)
- SmartRecruiters, JobVite, BambooHR, Breezy, Fountain, and more

### Gate 5: Domain/Company Mismatch

**Block:** Jobs where URL domain doesn't match company name.

**Why:** Cross-wired data indicates parser error or aggregator URLs.

**Examples (Blocked):**
- Company: `"Google"` + URL: `https://microsoft.com/jobs/123`

**Examples (Allowed):**
- Company: `"Google"` + URL: `https://careers.google.com/jobs/123`
- Company: `"Meta"` + URL: `https://metacareers.com/jobs/123`
- Company: `"OpenAI"` + URL: `https://boards.greenhouse.io/openai/jobs/123`

**Handled:** `domain_matches_company()` returns False → blocked. (Runs **after** fixture/dummy gate.)

### Gate 6: URL Probe (HTTP HEAD/GET) — Hard Fail vs Defer

**Block (Hard):** Jobs where URL returns 404 or other 4xx (except 429).

**Defer (Transient):** Jobs where URL returns 5xx, 429, timeout, or connection error — defer without marking was_notified, allows retry on next scan (`probe_deferred` counter).

**Probe Logic:**
1. Fixture/dummy / placeholder → local short-circuit `"bad"` (no HTTP)
2. Try HTTP HEAD first (faster)
3. Classify response:
   - **2xx/3xx** → `"good"` (alert)
   - **4xx except 429** → `"bad"` (hard block)
   - **5xx, 429** → `"error"` (transient, defer)
   - **Timeout/connection error** → `"error"` (transient, defer)
4. Accept 403 for job-shaped URLs (`/job`, `/career`, `/position`, `/apply`, `/intern`) — some ATSs block HEAD but allow browser GET

**Transient vs Hard Failures:**
- **Transient** (5xx, 429, timeout, connection errors): Write JSONL, skip live alerts, do NOT mark `was_notified` → later scans can retry
- **Hard** (404, 4xx except 429, empty URL, fixture/dummy hosts): Permanent block, no Discord/ntfy/Telegram/Notion

**Controlled by:** `JOBRADAR_LINK_PROBE` env var (default `1` in production; `0` in pytest).

**Timeout:** 8 seconds per URL (3s for notify-path probe).

**Handled:** `probe_url()` / `detailed_probe_url()` return `"good"`, `"bad"`, or `"error"`; `has_transient_probe_failure()` checks for defer condition.

### Gate 7: Notify Window (Recency)

**Block:** Jobs outside the notify window (default **14 days**).

**Why:** Avoid alerting about weeks-old postings that JobRadar just discovered.

**Prefer `posted_at` over `first_seen_at`:**
- `posted_at`: When the company/aggregator published the listing
- `first_seen_at`: When JobRadar first saw the listing

**Default behavior (`JOBRADAR_REQUIRE_POSTED_AT=1`):**
- If `posted_at` is missing, block (do not fall back to `first_seen_at`)
- This prevents floods of older Simplify/aggregator rows discovered in bulk

**Legacy fallback (`JOBRADAR_REQUIRE_POSTED_AT=0`):**
- If `posted_at` is missing, fall back to `first_seen_at`

**Window tuning:** Set `JOBRADAR_NOTIFY_WINDOW_DAYS=N` (canonical default **14**). Local `.env` may override (e.g. `3`) — tests clear that override via `JOBRADAR_SKIP_DOTENV` / conftest.

**Handled:** `within_notify_window()` returns False → blocked.

## Classification Recall (Overnight #39)

Recall-first classification keeps borderline technical roles that would otherwise match exclude-list patterns:

- **Technical Account Manager (TAM)** — kept via `strong_signals`
- **Technical Product Manager (TPM)** — kept via `strong_signals`
- Unknown / ambiguous roles → keep rather than drop

Clear non-technical roles (nursing, tax analyst, HR, marketing, real estate, …) stay excluded.

## Deferral Categories (Overnight #21, PR #39)

JobRadar tracks three types of deferrals that allow jobs to retry on later scans without permanent blocking:

### 1. `probe_deferred` — Transient Probe Failures

**When:** URL probe returns 5xx, 429 (rate limit), timeout, or connection error.

**Behavior:**
- Write JSONL for persistence
- Skip live Discord/ntfy/Telegram alerts
- **Do NOT mark was_notified**
- Next scan will retry probe and alert if URL recovers

### 2. `alerts_paused` — Alerts Disabled

**When:** `JOBRADAR_ALERTS_ENABLED=0` (dry-run mode).

**Behavior:**
- Write JSONL and SQLite as usual
- Skip live Discord/ntfy/Telegram alerts
- **Do NOT mark was_notified**
- Next scan with alerts enabled will alert these jobs

### 3. `cap_deferred` — Alert Cap Overflow

**When:** More new jobs than `JOBRADAR_MAX_ALERTS_PER_SCAN` cap (when cap > 0).

**Behavior:**
- Alert up to N jobs (**priority companies first**, then Fortune 500, then others)
- Overflow jobs write JSONL but skip live alerts
- **Do NOT mark was_notified**
- Next scan can alert overflow jobs if within cap
- `stats.cap_deferred` counts overflow; `stats.alert_cap_hit` is True when cap reached

**Key principle:** Only hard failures (404, empty URL, fixture/dummy, domain mismatch, old posted_at) permanently block. Transient/operational issues defer without marking was_notified.

## All Gates Summary

| Gate | Checks | Function | Behavior |
|------|--------|----------|----------|
| HTML tags | Company/title fields | `_HTML_TAG.search()` | Hard block |
| Empty/placeholder URLs | `""`, `TBD`, `N/A`, no scheme | `is_placeholder_url()` | Hard block |
| Fixture/dummy URLs | `example.*`, `test.*`, localhost, … | `is_fixture_or_dummy_url()` (before domain-match) | Hard block |
| Generic career pages | `/careers`, `/jobs` without ID | `is_specific_job_url()` | Hard block |
| Domain mismatch | Company vs URL domain | `domain_matches_company()` | Hard block |
| URL probe (hard) | HTTP 404, 4xx except 429; fixture short-circuit | `probe_url()` → `"bad"` | Hard block |
| URL probe (transient) | HTTP 5xx, 429, timeout, connection error | `probe_url()` → `"error"` | Defer (retry later) |
| Notify window | `posted_at` (default) / `first_seen_at` | `within_notify_window()` | Hard block |

**Result:** Jobs passing all gates reach Discord/ntfy/Telegram. Transient probe failures defer without permanent block.

## Environment Variables (Validation Control)

### `JOBRADAR_ALERTS_ENABLED`

**Default:** `1` (alerts ON)

**Set to `0` for safe dry-run testing:**
- Scan processes sources normally
- Writes to SQLite and JSONL
- **Skips Discord/ntfy/Telegram webhooks**
- **Does NOT mark jobs as was_notified** (allows retry after re-enable)

```bash
JOBRADAR_ALERTS_ENABLED=0 python -m jobradar scan --once
```

### `JOBRADAR_LINK_PROBE`

**Default:** `1` (probe ON in production)

**Set to `0` to bypass URL probing:**
- Main quality gates still apply (fixture/dummy, domain mismatch, generic career pages, empty URLs)
- HTTP HEAD/GET probe skipped
- Useful for: offline testing, CI with no network access

```bash
JOBRADAR_LINK_PROBE=0 pytest
```

Tests automatically set `JOBRADAR_LINK_PROBE=0` unless explicitly testing probe logic.

### `JOBRADAR_REQUIRE_POSTED_AT`

**Default:** `1` (require posted_at)

- `1`: Block jobs missing `posted_at` (do not fall back to `first_seen_at`)
- `0`: If `posted_at` missing, fall back to `first_seen_at`

### `JOBRADAR_NOTIFY_WINDOW_DAYS`

**Default:** `14` (canonical)

**Sets the recency window for notifications (days).**

Examples:
- `14` — Only notify about jobs posted in the last 14 days (default)
- `7` — Notify about jobs posted in the last week
- `3` — Only notify about jobs posted in the last 3 days
- `-1` — Notify about all jobs (no recency filter)

### `JOBRADAR_MAX_ALERTS_PER_SCAN`

**Default:** `0` (unlimited)

**Caps live Discord/ntfy/Telegram alerts per scan run (optional).**

**Behavior:**
- JSONL writes are unlimited (all new jobs recorded)
- When cap > 0: Discord/ntfy/Telegram stop after N alerts (**priority-first** ordering)
- When cap = 0 (default): No artificial limit, all qualifying jobs alert
- Capped jobs are deferred (`cap_deferred`) — not permanently silenced — so later scans can alert them
- Jobs past cap **do NOT mark was_notified**
- `stats.alert_cap_hit` is True if cap was reached
- `stats.cap_deferred` shows count of jobs deferred due to cap

**Examples:**
- `0` — Unlimited alerts (default — you won't miss alert #16+)
- `15` — Max 15 live alerts per scan (priority first)
- `5` — Max 5 alerts (very conservative)

```bash
JOBRADAR_MAX_ALERTS_PER_SCAN=5 python -m jobradar scan --once
```

### `JOBRADAR_SKIP_DOTENV`

**Set by pytest conftest** (`=1`) so `cli.main()` does not re-apply local `.env` over test `delenv`.

**Production CLI:** unset / `0` — `main()` loads `.env` normally.

### `PYTEST_CURRENT_TEST`

**Set automatically by pytest.**

When set, `send_discord()`, `send_ntfy()`, and `send_telegram()` are blocked (return `"skipped"`).

**Never set this manually!**

## What Good Output Looks Like

### Good Classification

**Kept** (recall-first):
- "Software Engineer Intern"
- "Data Science Intern"
- "Machine Learning Engineer"
- "SWE Intern"
- "Technical Account Manager Intern" (TAM — #39)
- "Technical Product Manager Intern" (TPM — #39)
- "AI Research Intern"

**Excluded** (clear negatives):
- "Nursing Intern" (medical)
- "Tax Analyst Intern" (accounting)
- "HR Intern" (human resources)
- "Marketing Intern" (non-technical)

### Noisy Classification / False Positives

**OK to keep** (recall-first philosophy):
- "Product Manager Intern" (borderline technical)
- "Business Analyst Intern" (might involve data)
- "Operations Intern" (might involve systems)
- Unknown roles → keep rather than drop

**When to tune EXCLUDE** in `src/jobradar/classify.py`:
- Only if **clearly wrong** jobs consistently slip through
- **Recall-first principle**: false positives OK, missed jobs NOT OK

### Bad URLs / Domain Mismatch

**Never notified** (gates block):
- `example.com` / other fixture hosts or empty URL
- Company "Google" with URL `microsoft.com`
- URL returns 404 (hard) or transient probe failure (defer, no Discord)
- URL domain doesn't match company

**Safe to notify**:
- Company "Google" with URL `careers.google.com`
- Company "Meta" with URL `metacareers.com`
- URL returns 200 and passes all gates

**Note**: Old SQLite rows may have cross-wired company/URL until a fresh scan rewrites. Mismatch/probe/fixture gates block Discord regardless.

## Discord / ntfy Confirmation

After scan completes with `notified > 0`:

1. Check Discord `#job-alerts` (if webhook configured)
2. Check phone ntfy notifications (if topic configured)
3. Check Telegram (if bot configured)
4. Check `data/notifications.jsonl` (always written)

Expected format:
```
[PRIORITY] OpenAI
Software Engineer Intern | San Francisco, CA
simplify-summer-2027 | https://careers.openai.com/...

Building AGI safely. Seeking interns for core infrastructure.
```

**No [PRIORITY] tag** for non-priority companies.

## Standing Rules

### Never Do

- **DO NOT** scrape `pittcsc/Summer2027-Internships` (stale Simplify fork)
- **DO NOT** auto-apply to jobs
- **DO NOT** send email alerts (Discord/ntfy/Telegram only)
- **DO NOT** commit `.env` or `secrets/` directory
- **DO NOT** block alerts on missing Grok keys (fast path never waits)

### Always Do

- Run `pytest` before committing classification changes
- Let empty API keys skip gracefully (no exceptions)
- Prefer recall over precision (false positives OK)
- Validate URLs before Discord (fixture + probe gates)

## Troubleshooting

### Scan Fails with Missing Keys

**Check**: Health output shows "skipped until keys set"

**Fix**: Missing keys → graceful skip. If scan fails:
```bash
python -m jobradar health
pytest -v
```

Fast path must never wait on Grok or missing keys.

### No New Jobs After First Scan

**Expected**: First scan seeds DB without alerts. Run again:
```bash
python -m jobradar scan --once
```

Force alerts on first scan:
```bash
python -m jobradar scan --once --alert-all
```

### Too Many False Positives

**Tune carefully**:
1. Identify repeated false positive keywords
2. Add to `EXCLUDE` in `src/jobradar/classify.py`
3. Run `pytest` to validate
4. Test with `scan --once`

**Remember**: Recall-first. Better to notify 10 borderline jobs than miss 1 real one.

### Old DB Has Wrong Company/URL Pairs

**Cause**: SQLite may have rows from before URL verification gates.

**Fix**: Fresh scan rewrites entries. Gates block Discord for mismatches/fixtures.

**Nuclear option:**
```bash
rm data/jobradar.db
python -m jobradar scan --once
```

First scan seeds without alerts. Second scan notifies.

## Success Criteria

✅ `pytest` passes (all green)
✅ `python -m jobradar validate-scan` passes (offline harness)
✅ `health` shows all adapters configured or gracefully skipped (incl. scout staleness)
✅ `scan --once` completes without exceptions
✅ `kept` count matches expected (no mass exclusion)
✅ `notified` count reasonable (first run: 0, later: N new jobs)
✅ Discord/ntfy/Telegram receive only valid URLs
✅ No fixture/dummy hosts or empty URLs in notifications
✅ Classification matches recall-first principle (incl. TAM/TPM)

## Next Steps

After validation:

1. Production: `python -m jobradar scan --loop --interval 300`
2. Monitor: Check Discord/ntfy for quality
3. Tune: Only if repeated clear negatives leak
4. Gmail: Optional, see [docs/ACCOUNTS.md](ACCOUNTS.md)
5. Notion: Optional backfill, see [docs/ACCOUNTS.md](ACCOUNTS.md)
6. Grok Bots: Optional analysis, see [docs/GROK_BOT_SETUP.md](GROK_BOT_SETUP.md)

Fast path never waits. Missing keys → skip gracefully.
