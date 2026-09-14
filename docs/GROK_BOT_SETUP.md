# Grok Bot setup (this Mac)

Cursor cannot create or deploy Grok Bots. You do this in the **Grok Bot app**. Groq.com (Llama API) is a different product and is not required for this.

Full Director brain (attach this to the Director Bot): [`../UPLOAD_TO_GROK_BOT.md`](../UPLOAD_TO_GROK_BOT.md)

## Order

1. Create **JobRadar Director** from [`../agents/grok/director.spec.md`](../agents/grok/director.spec.md). Attach `UPLOAD_TO_GROK_BOT.md`. Give it computer access to `job-agent-notifier/`.
2. Let Director start coding. Do not wait.
3. Create the five specialist Bots from the specs in `agents/grok/`. One webhook routine each. Paste `crsr_` keys into `job-agent-notifier/.env` (never git).
4. Ping each Bot with the command in its spec. Check **Run history**. HTTP 200 means the run started, not finished.

## Five specialists

| App name | Spec | .env webhook / key |
|---|---|---|
| JobRadar Analyst | `agents/grok/job-analyst.spec.md` | `GROK_BOT_WEBHOOK_JOB_ANALYST` / `GROK_BOT_KEY_JOB_ANALYST` |
| JobRadar Resume Mapper | `agents/grok/resume-mapper.spec.md` | `GROK_BOT_WEBHOOK_RESUME_MAPPER` / `GROK_BOT_KEY_RESUME_MAPPER` |
| JobRadar Strategist | `agents/grok/recruiting-strategist.spec.md` | `GROK_BOT_WEBHOOK_STRATEGIST` / `GROK_BOT_KEY_STRATEGIST` |
| JobRadar Inbox | `agents/grok/inbox-analyst.spec.md` | `GROK_BOT_WEBHOOK_INBOX` / `GROK_BOT_KEY_INBOX` |
| JobRadar Weekly | `agents/grok/weekly-reporter.spec.md` | `GROK_BOT_WEBHOOK_WEEKLY` / `GROK_BOT_KEY_WEEKLY` |

## Clicks for every Bot

1. Open **Grok Bot** → **Create your own**.
2. Paste Name, Title, Description from the spec.
3. Set plugins (Inbox: Gmail later; others none).
4. **View conversation details** → **Routines** → new → **When to run: Webhook**.
5. Save. Leave **Active** on. Open the routine again.
6. Copy **POST to** (`https://api2.cursor.sh/automations/webhook/…`) and **key** (`crsr_…`).
7. Register with the parent CLI if you want IDE pings:

```bash
cd "/Users/rohankilaru/Resume Bot"
node tools/grok-bot/grok-bot.js init
node tools/grok-bot/grok-bot.js add <routine-name> \
  --url 'https://api2.cursor.sh/automations/webhook/<id>' \
  --key 'crsr_…' \
  --description '<Title>'
```

Keys also belong in `~/.config/grok-bot/secrets.json` (mode 600) when using that CLI.

## Rules

- 50 routines per Bot. Last 20 runs kept.
- Anyone with URL + key can start a run.
- Disabled routine → 400. Bad key → 401.
- Do not use unofficial gateway port 1340.
- These Bots run on **this Mac**. A later VM can run Python 24/7. Bots stay here until you change the Bot's computer in the app.
- Python alerts must work even if every Grok Bot is offline.

## Docs

- [Grok Bot onboarding](https://cursor.com/help/grok-bot/onboarding.md)
- [Routines / webhooks](https://cursor.com/help/grok-bot/routines.md)
- Parent bridge: `/Users/rohankilaru/Resume Bot/tools/grok-bot/README.md`
