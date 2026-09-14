# Grok Bot spec: JobRadar Weekly

Cursor has no public API to create or deploy a Grok Bot. Paste this into the Grok Bot app.

## Create Bot

1. Open **Grok Bot**.
2. **Create your own**.
3. Paste the fields below.

**Name:** JobRadar Weekly

**Title:** JobRadar Weekly Reporter

**Description:**

When woken with action weekly_report, read JobRadar data if this computer can see job-agent-notifier/data/. Write a weekly recruiting report: new jobs, notified count, applications inferred, ghosts, next actions. Do not SMS the report unless Rohan asked.

## Plugins

- (none)

## Computer

Write: `/Users/rohankilaru/Resume Bot/job-agent-notifier/docs/weekly/`
Read: `/Users/rohankilaru/Resume Bot/job-agent-notifier/data/`

## Webhook routine

1. Open this Bot → **View conversation details** → **Routines**.
2. New routine. Name: `jobradar-weekly`.
3. **When to run:** Webhook.
4. Save, leave **Active** on, open again.
5. Copy **POST to** and **key**.

```
GROK_BOT_WEBHOOK_WEEKLY=https://api2.cursor.sh/automations/webhook/<id>
GROK_BOT_KEY_WEEKLY=crsr_…
```

```bash
cd "/Users/rohankilaru/Resume Bot"
node tools/grok-bot/grok-bot.js add jobradar-weekly \
  --url 'https://api2.cursor.sh/automations/webhook/<id>' \
  --key 'crsr_…' \
  --description 'JobRadar Weekly Reporter'
```

### Routine instruction

You were woken by JobRadar-AI via webhook.
action should be weekly_report.
Write docs/weekly/YYYY-MM-DD.md under job-agent-notifier if you can write files.
Include: new listings, alerts sent, priority company hits, open loops.
Never SMS/Discord/email the report unless Rohan asked.
Reply with the file path and 5 bullets.

A 200 response only means the run started. Check **Run history**.
