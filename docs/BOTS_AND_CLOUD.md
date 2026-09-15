# Grok Bots vs cloud automation

Your six Grok Bots are documented in [`agents/grok/`](../agents/grok/). Specs:

| Bot | Spec | What it does |
|---|---|---|
| Director | `director.spec.md` | Lead architect; wakes specialists after alerts |
| Job Analyst | `job-analyst.spec.md` | Two-line summary + role family + fit |
| Resume Mapper | `resume-mapper.spec.md` | Match resume bullets to a role |
| Strategist | `recruiting-strategist.spec.md` | Rank what to apply to today |
| Inbox Analyst | `inbox-analyst.spec.md` | Classify mail → Gmail labels |
| Weekly Reporter | `weekly-reporter.spec.md` | Write `docs/weekly/YYYY-MM-DD.md` |

Grok Bots run on **your Mac** via Cursor Automations webhooks (`GROK_BOT_WEBHOOK_*` in `.env`). They share weekly run limits.

## What replaces what (laptop closed)

| Need | Grok Bot (Mac) | Replacement (24/7) | Status |
|---|---|---|---|
| Scout new jobs | Director (indirect) | **GitHub Actions `cloud-scan`** every 30 min | ✅ PR #17 |
| Discord/ntfy alerts | — | Same workflow | ✅ |
| Notion board updates | — | Same workflow | ✅ |
| Gmail classify + label | Inbox Analyst | **`gmail-sync`** in cloud-scan | ✅ code + secrets |
| Gmail deep backfill | Inbox Analyst | **`gmail-reorganize --days 365`** once locally | ✅ this PR |
| Job summaries (LLM) | Job Analyst | Not automated yet — optional `GROQ_API_KEY` in Actions later | ⏳ |
| Resume bullet match | Resume Mapper | Needs your resume file on runner — keep on Mac or add secret | ⏳ |
| Daily prioritize | Strategist | Tier routing + Notion **Priority Active** view | ✅ partial |
| Weekly report | Weekly Reporter | **`weekly-report` GitHub Action** (stats markdown) | ✅ this PR |

## Can a script "spawn cloud agents" like Grok Bots?

**Not really in the way you might hope.**

- Grok Bots **are** Cursor Automations (webhook URLs). Same weekly limits apply whether triggered from Python or manually.
- **Cloud Agents** (this chat) are full VMs — great for one-off cleanup like today's Gmail refactor, but there is no public API to spawn unlimited scheduled cloud agents from a repo script.
- **`cursor-subscriptions` timers** can enqueue follow-ups to **one** existing cloud agent conversation — useful for reminders, not a fleet of bots.

**Practical 24/7 stack:**

```
GitHub Actions (cloud-scan, weekly-report)
    ↓
Python jobradar (scout + gmail-sync + SQLite)
    ↓
Discord / Notion / Gmail labels

Optional slow path (when under limit):
    Grok Bot webhooks on Mac for LLM summaries
```

## If you hit Groq Bot weekly limits

1. **Merge PR #17** and set GitHub Actions secrets — core pipeline no longer needs bots.
2. Use Notion views (**Pipeline**, **Needs Action**, **Priority Active**) instead of Strategist for daily focus.
3. Run **`gmail-reorganize`** once instead of Inbox Analyst backfill.
4. Reserve remaining Grok runs for high-value only: Resume Mapper on priority interviews.

## Optional future: Groq API in GitHub Actions

`.env.example` has `GROQ_API_KEY` but Python does not call it yet. A small post-scan step could replace Job Analyst for priority jobs only — without Mac webhooks. Not built in this PR; say if you want it next.
