# JobRadar-AI — Handoff for Cursor (post-MVP)

**Repo:** https://github.com/rohankilaru-ai/jobradar-ai  
**Local:** `/Users/rohankilaru/Resume Bot/job-agent-notifier/`  
**Branch:** `main`

## What works now (MVP)

Python scout → parse → classify → dedupe → SQLite → mock notify JSONL.

```bash
cd "/Users/rohankilaru/Resume Bot/job-agent-notifier"
source .venv/bin/activate   # or: python3 -m venv .venv && pip install -e ".[dev]"
pytest
python -m jobradar health
python -m jobradar scan --once
python -m jobradar ping-grok
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

## Next (MVP → production)

1. Live `scan --once` validation; tune classify exclude list if noisy
2. Optional: Twilio SMS + Discord webhook (`.env.example`)
3. Wire Director `.env` keys; confirm `ping-grok`
4. Notify only jobs first-seen within 14 days (backfill older into DB silently)
5. GitHub Actions already runs pytest
6. Later: Gmail inbox bot (Phase 4), 24/7 VM for Python loop
7. Do **not** scrape `pittcsc/Summer2027-Internships`

## Key modules

- `src/jobradar/parsers.py` — JSON + Simplify HTML (`↳`, Inactive)
- `src/jobradar/scout.py` — ETag cache; `sources=[]` means no sources (not all)
- `src/jobradar/pipeline.py` — end-to-end
- `src/jobradar/grok.py` — optional webhooks, 8s timeout
- Specs: `agents/grok/*.spec.md`

## Standing rules

Priority: notification speed. False positives OK. Missed jobs not OK.  
No auto-apply. No email alerts.
