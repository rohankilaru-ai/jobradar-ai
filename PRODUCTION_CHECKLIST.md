# JobRadar-AI Production Checklist

**Current Status:** MVP complete, pytest green (38 tests), free notification channels working.

**Completed:**
- ✅ Core pipeline: scout → parse → classify → dedupe → SQLite → notify
- ✅ Free notification channels: Discord, ntfy.sh phone push, Telegram
- ✅ 14-day notify window (backfill older jobs silently)
- ✅ Parser hardening (HTML-in-company, trailing-quote URLs)
- ✅ Notify idempotency across all channels
- ✅ Empty API keys skip gracefully (fast path never blocked)
- ✅ Notion board integration (optional)
- ✅ Gmail sync for tracking (optional)
- ✅ Product-completion test suite (offline validation)

---

## Remaining Production Gaps

### 1. Grok Bot Director Webhook (Phase 3)

**Status:** Client code ready, awaiting Rohan's Grok Bot UI webhook URL exposure.

**What's needed:**
- Rohan to expose Director webhook URL in Grok Bot desktop app UI
- Set `GROK_BOT_WEBHOOK_DIRECTOR` in `.env`
- Optional: specialist bot webhook URLs for fan-out (Analyst, Resume Mapper)

**Current behavior:**
- If Director webhook env var is empty → skip (fast path unblocked) ✅
- If set → POST compact JobRecord JSON, 8s timeout, errors logged but never crash notify

**Test command:**
```bash
python -m jobradar ping-grok
```

**Files:**
- `src/jobradar/grok.py` — webhook client
- `src/jobradar/director.py` — enqueue logic
- `agents/grok/*.spec.md` — bot specifications

---

### 2. Gmail Inbox Bot (Phase 4)

**Status:** Sync logic implemented, not yet running in loop.

**What's needed:**
- Run `python -m jobradar gmail-auth` once for OAuth tokens
- Optional: background job or cron to run `gmail-sync` every N hours

**Current behavior:**
- CLI commands work (`gmail-auth`, `gmail-sync --days 7`)
- Classifies emails: Applied, OA, Reject, Other
- Updates `applications` table with Gmail thread links
- Does NOT send email alerts (per standing rules) ✅

**Files:**
- `src/jobradar/gmail.py`
- `secrets/gmail-client.json` (user-provided OAuth2 credentials)
- `secrets/gmail-token.json` (generated after auth)

**Note:** Gmail is optional; notification alerts are already working via Discord/ntfy/Telegram.

---

### 3. 24/7 scanning (laptop closed)

**Status:** Implemented via GitHub Actions — see [docs/CLOUD_SCAN.md](docs/CLOUD_SCAN.md).

**What's needed (Rohan):**
- Add Discord / Notion / optional Gmail JSON as GitHub Actions secrets
- Enable Actions; run **cloud-scan** once manually to verify

**Optional local:**
- `python -m jobradar scan --loop --interval 300` on Mac/VM
- Prefer cloud-scan so sleep/travel does not stop alerts

**Files:**
- `Dockerfile` + `docker-compose.yml` (container option)
- `.env.example` (copy to `.env` and fill keys)

**Commands:**
```bash
# One-shot scan (manual testing)
python -m jobradar scan --once

# Loop forever (production)
python -m jobradar scan --loop --interval 300
```

---

## Validation Checklist

Before going live:

- [ ] **Run live scan validation:**
  ```bash
  python -m jobradar scan --once
  ```
  Review output for noisy exclusions; tune `EXCLUDE` list in `src/jobradar/classify.py` only if clearly wrong.

- [ ] **Verify notification channels:**
  ```bash
  python -m jobradar test-discord
  python -m jobradar test-ntfy
  python -m jobradar test-telegram
  ```

- [ ] **Check health:**
  ```bash
  python -m jobradar health
  ```

- [ ] **Confirm Grok Bot webhooks (when ready):**
  ```bash
  python -m jobradar ping-grok
  ```

- [ ] **Verify DB persistence:**
  ```bash
  ls -lh data/jobradar.db
  sqlite3 data/jobradar.db "SELECT COUNT(*) FROM jobs;"
  ```

- [ ] **Review notifications log:**
  ```bash
  head -20 data/notifications.jsonl
  ```

---

## Standing Rules (Never Change)

1. **Fast path never waits on Grok Bots or missing API keys** ✅
2. **False positives OK. Missed jobs not OK.** (recall-first classification) ✅
3. **No auto-apply** ✅
4. **No email alerts** (Discord/ntfy/Telegram only) ✅
5. **Do not scrape `pittcsc/Summer2027-Internships`** (stale Simplify fork) ✅

---

## Next Steps (Priority Order)

1. **Live-validate `scan --once`** with real GitHub sources (one-shot test)
2. **Wire Director webhook** when Rohan exposes URL in Grok Bot app
3. **Deploy to 24/7 VM** or run loop on Mac
4. **Optional: Gmail sync** (run `gmail-auth`, schedule periodic syncs)

**All critical features are complete. The system is production-ready for manual `scan --once` testing today.**
