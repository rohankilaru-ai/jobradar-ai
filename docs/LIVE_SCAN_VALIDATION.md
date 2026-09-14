# Live Scan Validation Guide

This guide walks you through validating a live `scan --once` without guessing. Use this after initial setup or when tuning classification rules.

## Prerequisites

1. Python 3.11+ with venv
2. `.env` file exists (copy from `.env.example` if missing)
3. No secrets required for basic validation; Discord/ntfy/Telegram optional

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

All tests should pass. This validates:
- Classification rules (include/exclude keywords)
- Dedupe logic
- Database operations
- CLI command registration
- Notification logic (mocked, no live Discord)

### 3. Health Check

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

### 4. Live Scan (once)

```bash
python -m jobradar scan --once
```

**First run** (empty DB):
```
first scan seeded=N jobs (no alerts). next scan will notify only new listings.
scan done fetched=X kept=Y new=N notified=0
```

**Subsequent runs**:
```
scan done fetched=X kept=Y new=Z notified=Z
```

Where:
- `fetched` = total job listings parsed from all sources
- `kept` = listings passing classification (not excluded)
- `new` = listings not seen before
- `notified` = new listings sent to Discord/ntfy/Telegram/JSONL

### 5. Optional: Link Verification (if on a branch with verify-links)

```bash
python -m jobradar verify-links
```

This validates URLs before Discord/ntfy fire. Check for:
- No `example.com` or empty URLs leak through
- Company/URL domain mismatch caught
- Only probed-good URLs reach notifications

## What Good Output Looks Like

### Good Classification

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
