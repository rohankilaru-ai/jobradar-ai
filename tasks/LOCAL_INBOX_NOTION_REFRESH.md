# Task: Local inbox + Notion refresh (new applications)

**Where:** run on your Mac in Cursor Desktop (not required on cloud).  
**Playbook:** [`agents/local/README.md`](../agents/local/README.md)  
**Paste prompt:** [`agents/local/ORCHESTRATOR.md`](../agents/local/ORCHESTRATOR.md)

## Checklist

- [ ] Repo open locally; `.env` has `NOTION_TOKEN` + `NOTION_DATABASE_ID`
- [ ] `secrets/gmail-client.json` present; `python -m jobradar gmail-auth` done once
- [ ] Fast path: `./scripts/local-inbox-notion-sync.sh 30`
- [ ] Or Agent path: paste `ORCHESTRATOR.md` → subagents 01→04
- [ ] Gmail sidebar `JobRadar/Applied` shows new apps
- [ ] Notion Tracker Status matches
- [ ] Read verify report; handle any `uncertain` leftovers

## One-liner for Cursor Agent

```
@agents/local/ORCHESTRATOR.md I applied to a bunch of new jobs — refresh Gmail JobRadar labels and Notion status for the last 30 days. Prefer the Python CLI if health shows gmail+notion configured; otherwise run subagents 01–04.
```
