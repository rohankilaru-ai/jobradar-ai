# Orchestrator — Local inbox + Notion refresh

You are running **on Rohan's Mac** in the JobRadar repo. Goal: catch **newly applied** (and progressed) job emails, label them under nested `JobRadar/*`, and mirror status into Notion — same outcome as the prior cloud inbox pass.

## Prefer Python CLI when possible

If `python -m jobradar health` shows `gmail: configured` and `notion: configured`:

```bash
python -m jobradar gmail-reorganize --days 30 --dry-run
python -m jobradar gmail-reorganize --days 30
python -m jobradar gmail-sync --days 14
python -m jobradar weekly-report
```

Then run **only** subagent `04-verify-report.md` (MCP spot-check). Skip 01–03.

If Gmail/Notion CLI is not configured, use Gmail + Notion MCP and spawn subagents **01 → 02 → 03 → 04** in order. Pass each subagent the prior agent's short JSON summary.

## Hard rules (all subagents)

1. Labels: parent `JobRadar` + **exactly one** nested status (`Applied`, `Waiting`, `OA`, `Interview`, `Final Round`, `Offer`, `Rejected`, `Ghosted`, `Recruiter`, `Backlog`).
2. Forward-only: highest stage wins; strip other nested status labels on the thread.
3. Skip: Gradescope, course mail, Handshake marketing digests, pure newsletters.
4. Include: ATS “thank you for applying”, Handshake “Application sent”, Greenhouse/Lever/Workday confirmations, OA/interview/reject mail.
5. Notion: update Status, Date applied (when Applied), Gmail thread URL, Company, Role when known. Do not invent companies.
6. Do not send Discord, email, or SMS. Inbox + Notion only.
7. After finishing, write a brief count: labeled / Notion upserted / skipped / uncertain.

## Repo references

- Label design: `docs/GMAIL_ORGANIZATION.md`
- Subagent prompts: `agents/local/subagents/*.md`
- Fast shell: `scripts/local-inbox-notion-sync.sh`

## Success criteria

- Recent application threads visible under Gmail sidebar `JobRadar/Applied` (and other statuses as appropriate).
- Matching Notion Tracker rows show the same Status (and Date applied when applicable).
- Verify report lists 5 example threads with Gmail link + Notion status.
