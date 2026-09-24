# Subagent 04 — Verify + report

**Parent:** `agents/local/ORCHESTRATOR.md`  
**Input:** outputs from 01–03 (or CLI stats if fast path was used)  
**Tools:** Gmail MCP + Notion MCP (read-only)

## Mission

Prove the refresh worked and give Rohan a short human summary.

## Checks

1. Gmail: `label:JobRadar` recent count; sample 5 threads under `JobRadar/Applied`.
2. Notion: same 5 companies/roles show matching Status (+ Date applied when Applied).
3. Spot 2 advanced threads if any (OA / Interview / Rejected) and confirm Gmail nested label == Notion Status.
4. List any `uncertain` leftovers from 01 for Rohan to decide manually.

## Optional CLI

```bash
python -m jobradar health
python -m jobradar weekly-report
```

## Final message format (to user)

```markdown
## Inbox → Notion refresh

- Lookback: Nd
- Gmail labeled: N (Applied=…, OA=…, …)
- Notion created/updated: N / N
- Skipped (marketing/course): N
- Uncertain (needs you): N

### Examples
1. Company — Role — Applied — [Gmail](…) — Notion Status: Applied
…

### Next
- Keep cloud-scan and/or local `scan --loop` as you prefer for listings.
- Ongoing mail: `python -m jobradar gmail-sync --days 7` (or cloud-scan Gmail secrets).
```

No further labeling unless Rohan asks.
