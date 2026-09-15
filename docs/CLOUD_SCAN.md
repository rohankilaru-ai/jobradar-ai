# Cloud scan (laptop closed)

JobRadar scans internship sources **24/7 on GitHub Actions**. The Mac LaunchAgent is optional and should **not** Discord when cloud is healthy (separate DBs → duplicate alerts).

## How it works

Workflow: [`.github/workflows/cloud-scan.yml`](../.github/workflows/cloud-scan.yml)

- Runs every **10 minutes** at `:03,:13,:23,:33,:43,:53` UTC (offset from round minutes so GitHub is less likely to delay the cron)
- Also runnable manually: Actions → **cloud-scan** → **Run workflow**
- **Fails** if Discord webhook secrets are missing (so a “green” run always means alerts can fire)
- Restores/saves `data/jobradar.db` via Actions cache so scans are incremental (not a fresh seed every time)
- Sends Discord / ntfy / Telegram alerts when secrets are set
- Optionally runs `gmail-sync` when Gmail OAuth JSON secrets are set

Public repos get standard Actions minutes **free**. 10‑minute cron is allowed (GitHub minimum is 5). Cron can still slip a few minutes under load.

## Verify it’s working

1. Actions → **cloud-scan** → **Run workflow** → set `test_discord` = **true** → Run.
2. Confirm the run is green and Discord gets a short test message in each configured tier channel.
3. Check the run log for `scan done … alerted=N`. `alerted=0` with `new=0` means **no new dated jobs** — not a broken Discord path.
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

**Rule:** cloud owns Discord. On the Mac set `JOBRADAR_ALERTS_ENABLED=0` (or unload the LaunchAgent) so both never alert the same job.

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

5. Unload local scan (recommended):

```bash
launchctl bootout "gui/$(id -u)/com.rohankilaru.jobradar-scan"
# optional: keep plist from auto-starting at login
mv ~/Library/LaunchAgents/com.rohankilaru.jobradar-scan.plist \
   ~/Library/LaunchAgents/com.rohankilaru.jobradar-scan.plist.disabled
```

And in Mac `.env`: `JOBRADAR_ALERTS_ENABLED=0`.

## Stopping / controlling Discord spam

| Control | How |
|---|---|
| **Pause all alerts now** | GitHub → Actions → **cloud-scan** → `...` menu → **Disable workflow** |
| **Pause without disabling** | Settings → Actions → Variables → `JOBRADAR_ALERTS_ENABLED` = `0` |
| **Fewer alerts per run** | Variable `JOBRADAR_MAX_ALERTS_PER_SCAN` (default `15`) |
| **Stricter freshness** | Variable `JOBRADAR_NOTIFY_WINDOW_DAYS` (default `3`) |

By default cloud-scan only Discord-alerts jobs with a known **source post date** within 3 days (`JOBRADAR_REQUIRE_POSTED_AT=1`). Older undated Simplify rows no longer flood just because cloud first saw them today.

## Local loop (debug only)

```bash
# Only if you temporarily want Mac Discord again:
# JOBRADAR_ALERTS_ENABLED=1
python -m jobradar scan --loop --interval 300
```

Or `./scripts/run-scan-loop.sh`. Prefer cloud-scan for production.

## Cursor Cloud Agents

Cursor agents (with Gmail + Notion MCP) are great for **inbox cleanup, labeling, and Notion board hygiene**. They are not a substitute for the scheduled Python scout — use **cloud-scan** for 24/7 source scanning.
