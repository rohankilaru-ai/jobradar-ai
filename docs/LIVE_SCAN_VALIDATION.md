# Live Scan Validation Guide

This guide walks you through validating a live `scan --once` without guessing. Use this after initial setup, when tuning classification rules, or when verifying production readiness.

**Last Updated:** Sep 2026 (Overnight #30) — Refreshed for current main after transient probe-fail defer (overnight #21) and alert pause/cap defer (PR #39) shipped.

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

All tests should pass (514+ tests). This validates:
- Classification rules (include/exclude keywords)
- Dedupe logic
- Database operations
- CLI command registration
- Notification logic (mocked, no live Discord)
- Link probe and quality gates
- URL validation (empty URLs, generic career pages, domain mismatch)
- Notify window (posted_at vs first_seen_at)

### 3. Comprehensive Validation Harness

```bash
python -m jobradar validate-scan
```

**New in overnight #13:** End-to-end validation of scan health without live notifications.

This command runs a comprehensive validation covering:
- Health check (adapters configured or gracefully skipped)
- Classification smoke test (known good/bad jobs)
- Link probe test (empty URLs, example.com, placeholder detection)
- Quality gate test (domain mismatch, generic career pages, HTML in company/title)
- Notify window test (posted_at vs first_seen_at logic)
- Database operations (upsert idempotence, dedupe)

**Output format:**
```
JobRadar Scan Validation
========================

✓ Environment health check passed
✓ Classification logic validated (3/3 tests passed)
✓ Link probe gates validated (5/5 tests passed)
✓ Quality gates validated (4/4 tests passed)
✓ Notify window logic validated (3/3 tests passed)
✓ Database operations validated (2/2 tests passed)

All validation checks passed! ✨
```

If any check fails, the output shows which validation failed and why.

### 4. Health Check

```bash
python -m jobradar health
```

Expected output:
```
jobradar 0.1.0 ok
db: data/jobradar.db (N jobs, M applications)
notifiers: jsonl [+ discord] [+ ntfy] [+ telegram]
notion: configured | skipped until keys set
gmail: skipped until secrets/gmail-client.json
grok webhooks: configured | skipped until keys set
```

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

**Subsequent runs**:
```
<<<<<<< HEAD
scan done fetched=X kept=Y new=Z notified=Z alerted=0
sources: ok=4 not_modified=2 failed=0
  aprameyak-2027: 15 jobs
  dreamwork-2027: not_modified (304)
  applyguy-2027: 8 jobs
  simplify-summer-2027: 23 jobs
  simplify-offseason-2027: not_modified (304)
  vansh-summer-2027: 12 jobs
=======
scan done fetched=X kept=Y new=Z notified=Z alerted=0 probe_deferred=0
>>>>>>> 2481771 (overnight #30: refresh live scan validation docs/harness for main)
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
<<<<<<< HEAD
- `sources` = per-source breakdown showing which sources succeeded (ok), returned 304 (not_modified), or failed (error)
=======
- `probe_deferred` = new listings with transient probe failures (timeout/5xx/429), deferred without marking was_notified
>>>>>>> 2481771 (overnight #30: refresh live scan validation docs/harness for main)

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
- No `example.com` or empty URLs leak through
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

**Handled:** `is_placeholder_url()` returns True → blocked.

### Gate 3: Test/Example URLs

**Block:** Jobs with test fixture URLs.

**Why:** Test data should never reach production notifications.

**Examples:**
- `example.com`, `example.org`
- `localhost`, `127.0.0.1`
- `test.com`

**Handled:** `job_notify_block_reason()` checks for `example.com` / `example.org`.

### Gate 4: Generic Career Pages (Not Specific Job Postings)

**Block:** URLs pointing to general career homepages or search pages, not specific job postings.

**Why:** Generic `/careers` or `/jobs` pages are not actionable — users need a direct application link.

**Examples (Blocked):**
- `https://stripe.com/careers`
- `https://meta.com/jobs`
- `https://example.com/careers/search?q=intern`
- `https://greenhouse.io/jobs/results`

**Examples (Allowed):**
- `https://stripe.com/careers/job/1234` — specific job ID
- `https://boards.greenhouse.io/stripe/jobs/1234?gh_jid=1234` — Greenhouse job
- `https://jobs.lever.co/stripe/uuid` — Lever job
- `https://meta.com/careers/position/123` — specific position

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

**Why:** Cross-wired data indicates parser error or aggregator URLs (e.g., job listed as "Google" with a "Microsoft" URL).

**Examples (Blocked):**
- Company: `"Google"` + URL: `https://microsoft.com/jobs/123`
- Company: `"Stripe"` + URL: `https://example.com/job`

**Examples (Allowed):**
- Company: `"Google"` + URL: `https://careers.google.com/jobs/123`
- Company: `"Meta"` + URL: `https://metacareers.com/jobs/123` — domain variant OK
- Company: `"Jane Street"` + URL: `https://janestreet.com/apply` — slug match
- Company: `"OpenAI"` + URL: `https://boards.greenhouse.io/openai/jobs/123` — recruiting platform + company in path

**Recruiting Platform Allowlist:**
When URL is on a known recruiting platform (Greenhouse, Lever, Ashby, Workday, etc.), company slug MUST appear in the URL path. Otherwise, domain must match company slug.

**Company Slug Normalization:**
- Remove suffixes: `Inc`, `Corp`, `LLC`, `Ltd`, `Company`, `Co`
- Remove non-alphanumeric: `Jane Street` → `janestreet`
- Match is case-insensitive

**Handled:** `domain_matches_company()` returns False → blocked.

### Gate 6: URL Probe (HTTP HEAD/GET)

**Block (Hard):** Jobs where URL returns 404 or other 4xx (except 429) — permanent block, marks was_notified.

**Defer (Transient):** Jobs where URL returns 5xx, 429, timeout, or connection error — defer without marking was_notified, allows retry on next scan.

**Why:** Dead links (404) waste user time; transient failures (timeout/5xx) may recover.

**Probe Logic:**
1. Try HTTP HEAD first (faster)
2. Classify response:
   - **2xx/3xx** → `"good"` (alert)
   - **4xx except 429** → `"bad"` (hard block, permanent)
   - **5xx, 429** → `"error"` (transient, defer)
   - **Timeout/connection error** → `"error"` (transient, defer)
3. Accept 403 for job-shaped URLs (`/job`, `/career`, `/position`, `/apply`, `/intern`) — some ATSs block HEAD but allow browser GET

**Transient vs Hard Failures:**
- **Transient** (5xx, 429, timeout, connection errors): Write JSONL, skip live alerts, do NOT mark `was_notified` → later scans can retry
- **Hard** (404, 4xx except 429, empty URL, example.com): Permanent block, no Discord/ntfy/Telegram/Notion

**Controlled by:** `JOBRADAR_LINK_PROBE` env var (default `1` in production; `0` in pytest).

**Timeout:** 8 seconds per URL (3s for notify-path probe).

**Handled:** `probe_url()` returns `"good"`, `"bad"`, or `"error"`; `has_transient_probe_failure()` checks for defer condition.

### Gate 7: Notify Window (Recency)

**Block:** Jobs outside the notify window (default 14 days).

**Why:** Avoid alerting about weeks-old postings that JobRadar just discovered.

**Prefer `posted_at` over `first_seen_at`:**
- `posted_at`: When the company/aggregator published the listing (parser extracts if available)
- `first_seen_at`: When JobRadar first saw the listing

**Default behavior (`JOBRADAR_REQUIRE_POSTED_AT=1`):**
- If `posted_at` is missing, block (do not fall back to `first_seen_at`)
- This prevents floods of older Simplify/aggregator rows discovered in bulk

**Legacy fallback (`JOBRADAR_REQUIRE_POSTED_AT=0`):**
- If `posted_at` is missing, fall back to `first_seen_at`

**Window tuning:** Set `JOBRADAR_NOTIFY_WINDOW_DAYS=N` (default 14).

**Handled:** `within_notify_window()` returns False → blocked.

## Deferral Categories (Overnight #21, PR #39)

JobRadar tracks three types of deferrals that allow jobs to retry on later scans without permanent blocking:

### 1. `probe_deferred` — Transient Probe Failures

**When:** URL probe returns 5xx, 429 (rate limit), timeout, or connection error.

**Behavior:**
- Write JSONL for persistence
- Skip live Discord/ntfy/Telegram alerts
- **Do NOT mark was_notified**
- Next scan will retry probe and alert if URL recovers

**Example:** Job URL times out during probe → deferred, not permanently silenced.

### 2. `alerts_paused` — Alerts Disabled

**When:** `JOBRADAR_ALERTS_ENABLED=0` (dry-run mode).

**Behavior:**
- Write JSONL and SQLite as usual
- Skip live Discord/ntfy/Telegram alerts
- **Do NOT mark was_notified**
- Next scan with alerts enabled will alert these jobs

**Example:** Testing classification changes without spamming channels.

### 3. `cap_deferred` — Alert Cap Overflow

**When:** More new jobs than `JOBRADAR_MAX_ALERTS_PER_SCAN` cap.

**Behavior:**
- Alert cap jobs (priority companies first)
- Overflow jobs write JSONL but skip live alerts
- **Do NOT mark was_notified**
- Next scan can alert overflow jobs if within cap

**Example:** 50 new jobs discovered, cap=15 → alert 15 (priority first), defer 35.

**Key principle:** Only hard failures (404, empty URL, domain mismatch, old posted_at) permanently block. Transient/operational issues defer without marking was_notified.

## All Gates Summary

| Gate | Checks | Function | Behavior |
|------|--------|----------|----------|
| HTML tags | Company/title fields | `_HTML_TAG.search()` | Hard block |
| Empty/placeholder URLs | `""`, `TBD`, `N/A`, no scheme | `is_placeholder_url()` | Hard block |
| Test URLs | `example.com`, `localhost` | Pattern match in `job_notify_block_reason()` | Hard block |
| Generic career pages | `/careers`, `/jobs` without ID | `is_specific_job_url()` | Hard block |
| Domain mismatch | Company vs URL domain | `domain_matches_company()` | Hard block |
| URL probe (hard) | HTTP 404, 4xx except 429 | `probe_url()` → `"bad"` | Hard block |
| URL probe (transient) | HTTP 5xx, 429, timeout, connection error | `probe_url()` → `"error"` | Defer (retry later) |
| Notify window | `posted_at` or `first_seen_at` | `within_notify_window()` | Hard block |

**Result:** Jobs passing all gates reach Discord/ntfy/Telegram. Transient probe failures defer without permanent block.

## Environment Variables (Validation Control)

These env vars control scan behavior during validation and production:

### `JOBRADAR_ALERTS_ENABLED`

**Default:** `1` (alerts ON)

**Set to `0` for safe dry-run testing:**
- Scan processes sources normally
- Writes to SQLite and JSONL
- **Skips Discord/ntfy/Telegram webhooks**
- **Does NOT mark jobs as was_notified** (allows retry after re-enable)
- Good for: validating classification, dedupe, and DB operations without spamming channels

**Deferred jobs:**
When alerts paused, stats show `alerts_paused=N` for jobs written but not marked as notified.

**Usage:**
```bash
JOBRADAR_ALERTS_ENABLED=0 python -m jobradar scan --once
```

### `JOBRADAR_LINK_PROBE`

**Default:** `1` (probe ON in production)

**Set to `0` to bypass URL probing:**
- Main quality gates still apply (domain mismatch, generic career pages, empty URLs)
- HTTP HEAD/GET probe skipped
- Useful for: offline testing, CI with no network access

**Usage:**
```bash
JOBRADAR_LINK_PROBE=0 pytest
```

**Note:** Tests automatically set `JOBRADAR_LINK_PROBE=0` unless explicitly testing probe logic.

### `JOBRADAR_REQUIRE_POSTED_AT`

**Default:** `1` (require posted_at)

**Behavior:**
- `1`: Block jobs missing `posted_at` (do not fall back to `first_seen_at`)
- `0`: If `posted_at` missing, fall back to `first_seen_at`

**Why default is `1`:**
Prevents notification floods when JobRadar discovers bulk aggregator data (e.g., Simplify's 2000+ historical listings all marked as "first seen today").

**When to set `0`:**
If you're OK with "first seen today" semantics and want to catch all new discoveries.

### `JOBRADAR_NOTIFY_WINDOW_DAYS`

**Default:** `14`

**Sets the recency window for notifications (days).**

**Examples:**
- `14` — Only notify about jobs posted in the last 14 days (default)
- `7` — Notify about jobs posted in the last week
- `3` — Only notify about jobs posted in the last 3 days
- `-1` — Notify about all jobs (no recency filter)

**Usage:**
```bash
JOBRADAR_NOTIFY_WINDOW_DAYS=7 python -m jobradar scan --once
```

### `JOBRADAR_MAX_ALERTS_PER_SCAN`

**Default:** `0` (unlimited)

**Caps live Discord/ntfy/Telegram alerts per scan run (optional).**

**Why:**
Optional spam control if a bulk source update dumps hundreds of new jobs at once.

**Behavior:**
- JSONL writes are unlimited (all new jobs recorded)
<<<<<<< HEAD
- When cap > 0: Discord/ntfy/Telegram stop after N alerts (priority-first ordering)
- When cap = 0 (default): No artificial limit, all qualifying jobs alert
- Capped jobs are deferred (not permanently silenced) so later scans can alert them
=======
- Discord/ntfy/Telegram stop after N alerts
- Jobs past cap **do NOT mark was_notified** (allows retry on next scan)
- Priority companies alert first, then others (priority-first ordering from overnight #19)
>>>>>>> 2481771 (overnight #30: refresh live scan validation docs/harness for main)
- `stats.alert_cap_hit` is True if cap was reached
- `stats.cap_deferred` shows count of jobs deferred due to cap

**Examples:**
- `0` — Unlimited alerts (default — you won't miss alert #16+)
- `15` — Max 15 live alerts per scan (priority first)
- `5` — Max 5 alerts (very conservative)

**Usage:**
```bash
JOBRADAR_MAX_ALERTS_PER_SCAN=5 python -m jobradar scan --once
```

### `PYTEST_CURRENT_TEST`

**Set automatically by pytest.**

**Safety guard:**
When set, `send_discord()`, `send_ntfy()`, and `send_telegram()` are blocked (return `"skipped"`).

**Why:**
Prevents test suite from accidentally firing live webhooks even if webhook URLs are configured in `.env`.

**Never set this manually!**

## What Good Output Looks Like

### Good Classification

**Kept** (recall-first):

**Kept** (recall-first):
- "Software Engineer Intern"
- "Data Science Intern"
- "Machine Learning Engineer"
- "SWE Intern"
- "Fullstack Developer Intern"
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
- Examples: "Dental Assistant Intern", "Real Estate Intern"
- Add to `EXCLUDE` tuple with specific keywords
- **Recall-first principle**: false positives OK, missed jobs NOT OK

### Bad URLs / Domain Mismatch

**Never notified** (gates block):
- `example.com` or empty URL
- Company "Google" with URL `microsoft.com`
- URL returns 404 or timeout
- URL domain doesn't match company

**Safe to notify**:
- Company "Google" with URL `careers.google.com`
- Company "Meta" with URL `metacareers.com`
- URL returns 200 and HTML contains company indicators

**Note**: Old SQLite rows may have cross-wired company/URL until a fresh scan rewrites. Mismatch/probe gates block Discord regardless.

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

## Classification Tuning Guide

### When NOT to Tune

- Unknown roles (keep them)
- Borderline technical roles (keep them)
- One-off false positives (acceptable)

### When to Tune

Only when **repeated clear negatives** slip through:

1. Identify the bad keyword: "dental", "real estate", "nursing"
2. Check if already in `EXCLUDE` tuple in `src/jobradar/classify.py`
3. If missing, add it:

```python
EXCLUDE = (
    "nursing", "nurse", "tax intern", "tax analyst", "accounting intern",
    "pharmacist", "dental", "medical assistant", "registered nurse",
    "social work", "hr intern", "human resources", "recruiter intern",
    "marketing intern", "sales intern", "real estate",
    "your-new-keyword",  # add here
)
```

4. Test: `pytest tests/test_classify_dedupe_notify.py -v`
5. Validate: `python -m jobradar scan --once` (check `kept` count)

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
- Validate URLs before Discord (probe gates)

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

**Fix**: Fresh scan rewrites entries. Gates block Discord for mismatches.

**Nuclear option**:
```bash
rm data/jobradar.db
python -m jobradar scan --once
```

First scan seeds without alerts. Second scan notifies.

## Success Criteria

✅ `pytest` passes (all green)
✅ `health` shows all adapters configured or gracefully skipped
✅ `scan --once` completes without exceptions
✅ `kept` count matches expected (no mass exclusion)
✅ `notified` count reasonable (first run: 0, later: N new jobs)
✅ Discord/ntfy/Telegram receive only valid URLs
✅ No `example.com` or empty URLs in notifications
✅ Classification matches recall-first principle

## Next Steps

After validation:

1. Production: `python -m jobradar scan --loop --interval 300`
2. Monitor: Check Discord/ntfy for quality
3. Tune: Only if repeated clear negatives leak
4. Gmail: Optional, see [docs/ACCOUNTS.md](ACCOUNTS.md)
5. Notion: Optional backfill, see [docs/ACCOUNTS.md](ACCOUNTS.md)
6. Grok Bots: Optional analysis, see [docs/GROK_BOT_SETUP.md](GROK_BOT_SETUP.md)

Fast path never waits. Missing keys → skip gracefully.
