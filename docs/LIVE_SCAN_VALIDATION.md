# Live Scan Validation Guide

This guide walks you through validating a live `scan --once` without guessing. Use this after initial setup, when tuning classification rules, or when verifying production readiness.

**Last Updated:** Sep 2026 (Overnight #13) — Refreshed for current main after quality gates, link verification, and notification gating shipped.

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

All tests should pass (262+ tests). This validates:
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
- **Skips Notion upsert** (does not flood Backlog)
- Grok webhooks still fire if configured (to test Director)

**First run** (empty DB):
```
first scan seeded=N jobs (no alerts). next scan will notify only new listings.
scan done fetched=X kept=Y new=N notified=0 alerted=0
```

**Subsequent runs**:
```
scan done fetched=X kept=Y new=Z notified=Z alerted=0
sources: ok=4 not_modified=2 failed=0
  aprameyak-2027: 15 jobs
  dreamwork-2027: not_modified (304)
  applyguy-2027: 8 jobs
  simplify-summer-2027: 23 jobs
  simplify-offseason-2027: not_modified (304)
  vansh-summer-2027: 12 jobs
```

Where:
- `fetched` = total job listings parsed from all sources
- `kept` = listings passing classification (not excluded)
- `new` = listings not seen before
- `notified` = new listings written to JSONL
- `alerted` = new listings sent to Discord/ntfy/Telegram (0 when JOBRADAR_ALERTS_ENABLED=0)
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

**Block:** Jobs where URL returns 404, timeout, or network error.

**Why:** Dead links waste user time; only alert for accessible postings.

**Probe Logic:**
1. Try HTTP HEAD first (faster)
2. If HEAD fails, try GET
3. Accept 2xx (success) or 3xx (redirect)
4. Accept 403 if URL contains job-related keywords (`/job`, `/career`, `/position`, `/apply`, `/intern`) — some ATSs block HEAD but allow browser GET
5. Block 404 (not found)
6. Block 5xx (server error)
7. Network timeout/error → block

**Controlled by:** `JOBRADAR_LINK_PROBE` env var (default `1` in production; `0` in pytest).

**Timeout:** 3 seconds per URL.

**Handled:** `probe_url()` returns False → blocked.

### Gate 7: Notify Window (Recency)

**Block:** Jobs outside the notify window (default 3 days).

**Why:** Avoid alerting about weeks-old postings that JobRadar just discovered.

**Prefer `posted_at` over `first_seen_at`:**
- `posted_at`: When the company/aggregator published the listing (parser extracts if available)
- `first_seen_at`: When JobRadar first saw the listing

**Default behavior (`JOBRADAR_REQUIRE_POSTED_AT=1`):**
- If `posted_at` is missing, block (do not fall back to `first_seen_at`)
- This prevents floods of older Simplify/aggregator rows discovered in bulk

**Legacy fallback (`JOBRADAR_REQUIRE_POSTED_AT=0`):**
- If `posted_at` is missing, fall back to `first_seen_at`

**Window tuning:** Set `JOBRADAR_NOTIFY_WINDOW_DAYS=N` (default 3).

**Handled:** `within_notify_window()` returns False → blocked.

## All Gates Summary

| Gate | Checks | Function |
|------|--------|----------|
| HTML tags | Company/title fields | `_HTML_TAG.search()` |
| Empty/placeholder URLs | `""`, `TBD`, `N/A`, no scheme | `is_placeholder_url()` |
| Test URLs | `example.com`, `localhost` | Pattern match in `job_notify_block_reason()` |
| Generic career pages | `/careers`, `/jobs` without ID | `is_specific_job_url()` |
| Domain mismatch | Company vs URL domain | `domain_matches_company()` |
| URL probe | HTTP HEAD/GET 2xx/3xx | `probe_url()` |
| Notify window | `posted_at` or `first_seen_at` | `within_notify_window()` |

**Result:** Only jobs passing all 7 gates reach Discord/ntfy/Telegram.

## Environment Variables (Validation Control)

These env vars control scan behavior during validation and production:

### `JOBRADAR_ALERTS_ENABLED`

**Default:** `1` (alerts ON)

**Set to `0` for safe dry-run testing:**
- Scan processes sources normally
- Writes to SQLite and JSONL
- **Skips Discord/ntfy/Telegram webhooks**
- Good for: validating classification, dedupe, and DB operations without spamming channels

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

**Default:** `3`

**Sets the recency window for notifications (days).**

**Examples:**
- `3` — Only notify about jobs posted in the last 3 days
- `7` — Notify about jobs posted in the last week
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
- When cap > 0: Discord/ntfy/Telegram stop after N alerts (priority-first ordering)
- When cap = 0 (default): No artificial limit, all qualifying jobs alert
- Capped jobs are deferred (not permanently silenced) so later scans can alert them
- `stats.alert_cap_hit` is True if cap was reached

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
