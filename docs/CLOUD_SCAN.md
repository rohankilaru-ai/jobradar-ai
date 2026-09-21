# Cloud scan (laptop closed)

JobRadar can Discord from **either** GitHub Actions (cloud) **or** the Mac LaunchAgent (local) — not both. Separate DBs → duplicate alerts if both are on.

## Flip switch (local ↔ cloud)

```bash
cd "/Users/rohankilaru/Resume Bot/job-agent-notifier"
./scripts/scan-mode.sh status   # what’s on
./scripts/scan-mode.sh local    # Mac on, cloud-scan workflow off
./scripts/scan-mode.sh cloud    # cloud on, Mac LaunchAgent off
```

| Mode | Discord from | Needs |
|---|---|---|
| `local` | Mac every ~5 min | Laptop awake |
| `cloud` | GitHub Actions (~5 min cron, may lag) | Secrets on the repo |

The script toggles: LaunchAgent, `.env` `JOBRADAR_ALERTS_ENABLED`, and `gh workflow disable/enable cloud-scan.yml`.

## How it works

Workflow: [`.github/workflows/cloud-scan.yml`](../.github/workflows/cloud-scan.yml)

- Runs every **5 minutes** (GitHub’s minimum) at `:02,:07,:12,…` UTC (offset from round minutes so GitHub is less likely to delay the cron)
- Also runnable manually: Actions → **cloud-scan** → **Run workflow**
- **Fails** if Discord webhook secrets are missing (so a “green” run always means alerts can fire)
- Restores/saves `data/jobradar.db` via Actions cache so scans are incremental (not a fresh seed every time)
- Sends Discord / ntfy / Telegram alerts when secrets are set
- Optionally runs `gmail-sync` when Gmail OAuth JSON secrets are set

Public repos get standard Actions minutes **free**. 5‑minute cron is allowed (GitHub’s minimum). ~288 runs/day × ~1 min ≈ a few hundred minutes/month — free on public; fine even on private Free (2,000 min). Cron can still slip a few minutes under load.

## Verify it’s working

1. Actions → **cloud-scan** → **Run workflow** → set `test_discord` = **true** → Run.
2. Confirm the run is green and Discord gets a short test message in each configured tier channel.
3. Check the run log for `scan done … alerted=N`. `alerted=0` with `new=0` means **no new dated jobs** — not a broken Discord path.
   - Per-source breakdown shows which sources succeeded (`ok`), returned `not_modified` (304), or failed with error details.
4. Confirm scheduled runs appear with `event: schedule` (not only `push`). After changing the cron, wait ~15–20 minutes for the next tick.

```bash
gh run list --workflow=cloud-scan.yml --limit 10
gh workflow run cloud-scan.yml -f test_discord=true
```

### Why overnight looked “dead,” then flooded

| What you saw | Cause |
|---|---|
| Overnight: no Discord | Mac asleep (local DNS fail). Cloud was scanning but **Discord secrets were empty** until ~16:42 UTC Sep 15 — so cloud could not post. |
| Open laptop → flood | Local LaunchAgent woke, saw jobs “new” to the **Mac** DB, Discord-on → dump. |
| After fixing secrets → another dump | First cloud runs with working webhooks + thin/empty cache treated listings as newly alertable. Spam gates (`REQUIRE_POSTED_AT`, 3‑day window, cap 15) now limit that. |
| Quiet for a while after | Normal: `alerted=0` when nothing new has a source `posted_at` within 3 days. |

**Rule:** one Discord owner at a time. Use `./scripts/scan-mode.sh local|cloud` — do not enable both.

## One-time setup (required for Discord)

**Without Discord secrets, cloud-scan fails on purpose** — otherwise it looks “green” while only your Mac can alert (which floods Discord when you open the laptop).

1. On your Mac, open `.env` and copy the Discord webhook line(s).
2. GitHub → repo → **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Required? |
|---|---|
| `DISCORD_WEBHOOK_URL` **or** `DISCORD_WEBHOOK_PRIORITY` / `_FORTUNE500` / `_OTHER` | **Required** (same values as Mac `.env`) |
| `NTFY_TOPIC` | Optional |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Optional |
| `NOTION_TOKEN` + `NOTION_DATABASE_ID` | Recommended (board updates) |

3. Optional Gmail sync (inbox → labels + Notion status):

| Secret | Value |
|---|---|
| `GMAIL_CLIENT_SECRETS_JSON` | Full contents of `secrets/gmail-client.json` |
| `GMAIL_TOKEN_JSON` | Full contents of `secrets/gmail-token.json` (from `python -m jobradar gmail-auth` on your Mac once) |

Refresh tokens expire if unused for long periods — re-run `gmail-auth` locally and update the secret if sync starts failing.

4. Trigger once with `test_discord=true`. Confirm Discord.

5. Prefer cloud overnight: `./scripts/scan-mode.sh cloud`. Prefer snappy Discord while coding: `./scripts/scan-mode.sh local`.

## Stopping / controlling Discord spam

| Control | How |
|---|---|
| **Pause all alerts now** | GitHub → Actions → **cloud-scan** → `...` menu → **Disable workflow** |
| **Pause without disabling** | Settings → Actions → Variables → `JOBRADAR_ALERTS_ENABLED` = `0` |
| **Optional alert cap** | Variable `JOBRADAR_MAX_ALERTS_PER_SCAN` (`0` = unlimited, default) |
| **Stricter freshness** | Variable `JOBRADAR_NOTIFY_WINDOW_DAYS` (default `3`) |

By default cloud-scan Discord-alerts **every** matching new job with a known **source post date** within 3 days (`JOBRADAR_REQUIRE_POSTED_AT=1`). No per-scan cap — you will not miss alert #16+. Older undated Simplify rows still do not flood just because cloud first saw them today.

## Local loop

Use the flip switch (`./scripts/scan-mode.sh local`). Under the hood that starts LaunchAgent → `scripts/run-scan-loop.sh` → `scan --loop` every 5 minutes.

## Cursor Cloud Agents

Cursor agents (with Gmail + Notion MCP) are great for **inbox cleanup, labeling, and Notion board hygiene**. They are not a substitute for the scheduled Python scout — use **cloud-scan** for 24/7 source scanning.
