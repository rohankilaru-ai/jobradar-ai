# Grok Bot spec: JobRadar Analyst

Cursor has no public API to create or deploy a Grok Bot. Paste this into the Grok Bot app.

## Create Bot

1. Open **Grok Bot**.
2. **Create your own**.
3. Paste the fields below.

**Name:** JobRadar Analyst

**Title:** JobRadar Job Analyst

**Description:**

When woken, read payload.job. Write a two-line opportunity summary: what the team likely does, why it fits a UC Berkeley Data Science student targeting SWE / DS / DE / AI / research. Flag location, season, and closed/locked if present. Do not notify Rohan. Do not apply. Python already alerted.

## Plugins

- (none)

## Webhook routine

1. Open this Bot → **View conversation details** → **Routines**.
2. New routine. Name: `jobradar-analyst`.
3. **When to run:** Webhook.
4. Save, leave **Active** on, open again.
5. Copy **POST to** and **key**.

```
GROK_BOT_WEBHOOK_JOB_ANALYST=https://api2.cursor.sh/automations/webhook/<id>
GROK_BOT_KEY_JOB_ANALYST=crsr_…
```

```bash
cd "/Users/rohankilaru/Resume Bot"
node tools/grok-bot/grok-bot.js add jobradar-analyst \
  --url 'https://api2.cursor.sh/automations/webhook/<id>' \
  --key 'crsr_…' \
  --description 'JobRadar Job Analyst'
node tools/grok-bot/grok-bot.js trigger jobradar-analyst --json '{"action":"ping","event":"jobradar.new_job","job":{"company":"TestCo","title":"Software Engineer Intern","location":"SF","url":"https://example.com","sources":["ping"],"snippet":"test","priority":false}}'
```

### Routine instruction

You were woken by JobRadar-AI via webhook.
Read payload.job only. Do not fetch giant GitHub READMEs.
Write:
1. Two-line summary.
2. Role family: SWE | DS | DE | ML | AI | Research | Quant | Infra | Other.
3. Fit for Rohan (Berkeley DS, internships 2026–2027): high | medium | stretch.
Never send SMS, Discord, or email. Ask before changing an external account.
Reply short.

A 200 response only means the run started. Check **Run history**.
