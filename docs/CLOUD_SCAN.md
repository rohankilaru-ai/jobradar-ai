# Cloud scan (laptop closed)

JobRadar can keep scanning internship sources **without your Mac awake** via GitHub Actions.

## How it works

Workflow: [`.github/workflows/cloud-scan.yml`](../.github/workflows/cloud-scan.yml)

- Runs every **30 minutes** at `:07` and `:37` UTC (offset from `:00`/`:30` so GitHub is less likely to delay the cron)
- Also runnable manually: Actions → **cloud-scan** → **Run workflow**
- **Fails** if Discord webhook secrets are missing (so a “green” run always means alerts can fire)
- Restores/saves `data/jobradar.db` via Actions cache so scans are incremental (not a fresh seed every time)
- Sends Discord / ntfy / Telegram alerts when secrets are set
- Optionally runs `gmail-sync` when Gmail OAuth JSON secrets are set

This replaces needing `python -m jobradar scan --loop` on a local machine.

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

4. Trigger once: **Actions → cloud-scan → Run workflow**. Confirm Discord/Notion update.

5. You can close your laptop. Scans continue on GitHub's runners.

## Stopping / controlling Discord spam

| Control | How |
|---|---|
| **Pause all alerts now** | GitHub → Actions → **cloud-scan** → `...` menu → **Disable workflow** |
| **Pause without disabling** | Settings → Actions → Variables → `JOBRADAR_ALERTS_ENABLED` = `0` |
| **Fewer alerts per run** | Variable `JOBRADAR_MAX_ALERTS_PER_SCAN` (default `15`) |
| **Stricter freshness** | Variable `JOBRADAR_NOTIFY_WINDOW_DAYS` (default `3`) |

By default cloud-scan only Discord-alerts jobs with a known **source post date** within 3 days (`JOBRADAR_REQUIRE_POSTED_AT=1`). Older undated Simplify rows no longer flood just because cloud first saw them today.

## Local loop (optional)

Still fine for development:

```bash
python -m jobradar scan --loop --interval 300
```

Prefer cloud-scan for production so sleep/travel does not stop alerts.

## Cursor Cloud Agents

Cursor agents (with Gmail + Notion MCP) are great for **inbox cleanup, labeling, and Notion board hygiene**. They are not a substitute for the scheduled Python scout — use **cloud-scan** for 24/7 source scanning.
