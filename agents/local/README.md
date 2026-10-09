# Local inbox → Notion agents (Mac)

Run the same Gmail + Notion job-app cleanup that the cloud agent did — **on your laptop**, with Cursor Agent + these markdown prompts.

## When to use

You applied to a bunch of new roles and want:

1. Recent application mail labeled under `JobRadar/*`
2. Notion Applications board Status / Date applied / Gmail thread updated
3. A short report of what changed

## Two ways to run

### A. Fast path (recommended when OAuth works)

```bash
cd "/Users/rohankilaru/Resume Bot/job-agent-notifier"   # or this repo clone
./scripts/local-inbox-notion-sync.sh                 # last 30 days
./scripts/local-inbox-notion-sync.sh 14              # last 14 days
./scripts/local-inbox-notion-sync.sh 30 --dry-run    # preview only
```

Requires `.env` with Notion keys + `secrets/gmail-client.json` + prior `python -m jobradar gmail-auth`.

### B. Cursor Agent + subagents (MCP / edge cases)

1. Open this repo in **Cursor Desktop** on your Mac (Gmail + Notion MCP connected).
2. Paste the contents of [`ORCHESTRATOR.md`](ORCHESTRATOR.md) as the chat message (or `@agents/local/ORCHESTRATOR.md`).
3. The orchestrator spawns the four subagents in order — each prompt lives under [`subagents/`](subagents/).

Prefer **A** for bulk labeling (Python API is faster and consistent). Use **B** when you need MCP judgment on ambiguous threads, Notion view hygiene, or OAuth is broken.

## Files

| File | Role |
|---|---|
| `ORCHESTRATOR.md` | Master prompt — paste into Cursor Agent |
| `subagents/01-gmail-discover.md` | Find new application threads |
| `subagents/02-gmail-label.md` | Apply `JobRadar` + one nested status |
| `subagents/03-notion-upsert.md` | Mirror status onto Tracker board |
| `subagents/04-verify-report.md` | Spot-check + summary for you |
| `../../tasks/LOCAL_INBOX_NOTION_REFRESH.md` | One-line task card / checklist |
| `../../scripts/local-inbox-notion-sync.sh` | CLI wrapper for path A |

## Do not

- Relabel Gradescope / course mail / Handshake marketing digests
- Remove cloud-scan Discord controls while doing inbox work
- Create flat legacy labels (`Applied`, `OA`, `Job Oriented`) — nested only
