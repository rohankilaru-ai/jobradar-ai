# JobRadar account setup

Do these in order. Paste secrets only in `.env` (never git). After each key:

```bash
cd "/Users/rohankilaru/Resume Bot/job-agent-notifier"
source .venv/bin/activate
python -m jobradar health
```

Copy env if missing: `cp .env.example .env`

---

## 1. Discord (alerts work as soon as the URL is set)

1. Discord → server (create `Rohan Jobs` if needed) → text channel `#job-alerts`.
2. Channel gear → **Integrations** → **Webhooks** → **New Webhook** named `JobRadar`.
3. Copy the URL into `.env`:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

4. Test:

```bash
python -m jobradar test-discord
```

Expect `ok` and a message in `#job-alerts`. Then:

```bash
python -m jobradar scan --loop
```

---

## 2. Phone push (free — no Twilio)

Twilio is **not** used. Use **ntfy** (recommended) and/or **Telegram**. Both are free for personal internship alerts. A few jobs per hour will not hit practical limits.

### 2a. ntfy (recommended)

Phone notification, no credit card, no bot setup.

1. Install **ntfy** on your phone ([ntfy.sh](https://ntfy.sh) → Apps: iOS / Android).
2. In the app: **Subscribe to topic**. Pick a long secret name only you know, e.g. `jobradar-rohan-x7k9m2q`. Do **not** use a short guessable name (public server).
3. `.env`:

```
NTFY_TOPIC=jobradar-rohan-x7k9m2q
NTFY_SERVER=https://ntfy.sh
```

4. Test:

```bash
python -m jobradar test-ntfy
```

Expect `ok` and a phone notification.

Optional later: self-host ntfy or use `NTFY_TOKEN` on a private server. Not required.

### 2b. Telegram (optional second channel)

1. In Telegram, message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the bot token.
2. Message your new bot once (say `hi`).
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser. Find `"chat":{"id": ...}` — that number is `TELEGRAM_CHAT_ID`.
4. `.env`:

```
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
```

5. `python -m jobradar test-telegram`

---

## 3. Notion board

1. [notion.so/my-integrations](https://www.notion.so/my-integrations) → **New integration** `JobRadar` (Internal). Copy the secret (`ntn_` or `secret_`).
2. New page `JobRadar` → `/data` → **Table - Full page** named `Applications`.
3. Properties (names must match):

| Property | Type | Notes |
|---|---|---|
| Name | title | `Company — Role` |
| Company | text | |
| Role | text | |
| Location | text | |
| URL | url | |
| Status | select | Seen, Applied, OA, Interview, Final Round, Offer, Rejected, Ghosted, Skip |
| Priority | checkbox | |
| Source | text | |
| First seen | date | |
| Last update | date | |
| Canonical key | text | hide this column |
| Gmail thread | url | |

4. Database **…** → **Connect to** → `JobRadar`.
5. Database URL: `notion.so/<32 hex chars>?v=…` → that hex is `NOTION_DATABASE_ID`.
6. `.env`:

```
NOTION_TOKEN=ntn_...
NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

7. `python -m jobradar test-notion`
8. Optional starter rows (priority companies only): `python -m jobradar notion-backfill --priority-only`

New jobs after the seed scan also upsert to Notion. Seeded 8k listings are **not** dumped automatically.

---

## 4. Gmail (Google Cloud desktop OAuth)

1. [console.cloud.google.com](https://console.cloud.google.com/) → project `jobradar`.
2. Enable **Gmail API**.
3. **OAuth consent screen**: External is OK. App name `JobRadar`. Add your Gmail as a **test user**.
4. Scopes (code requests these): `gmail.readonly`, `gmail.modify`.
5. **Credentials** → **OAuth client ID** → **Desktop app**. Download JSON to:

`job-agent-notifier/secrets/gmail-client.json`

6. `.env`:

```
GMAIL_CLIENT_SECRETS=secrets/gmail-client.json
GMAIL_TOKEN=secrets/gmail-token.json
```

7. `python -m jobradar gmail-auth` — browser login, writes `secrets/gmail-token.json`.
8. `python -m jobradar gmail-sync` — last 7 days, then incremental. Labels: Applied, Interview, OA, Rejected, Offer, Recruiter, Waiting. Email is never used as an alert.

---

## Sheets

Skip. Notion is the board. Two boards will drift.

---

## Grok Bots (optional)

See [GROK_BOT_SETUP.md](GROK_BOT_SETUP.md). Empty webhook env = skip.
