# Subagent 03 — Notion upsert (Applications / Tracker)

**Parent:** `agents/local/ORCHESTRATOR.md`  
**Input:** labeled list from `02-gmail-label`  
**Tools:** Notion MCP (`notion-search` / `notion-ai-search`, `notion-fetch`, `notion-query-data-sources`, `notion-update-page`, `notion-create-pages`)

## Mission

Mirror each labeled Gmail thread onto the **JobRadar Tracker / Applications** Notion database.

## Find the board

Search for the Applications / JobRadar Tracker database Rohan uses. Confirm properties include at least: Name, Company, Role, Status, Canonical key, Gmail thread, Date applied, Tier, Role family (create/update only properties that already exist — do not redesign the schema unless missing Status or Gmail thread).

## Per labeled thread

1. Build Gmail thread URL: `https://mail.google.com/mail/u/0/#inbox/<thread_id>`
2. Try to find an existing row by:
   - Gmail thread URL / id property, or
   - Company + Role fuzzy match
3. **Update** if found; **create** if not (Status from Gmail; Name like `{Company} — {Role}` or subject snippet).
4. Set when known:
   - `Status` = nested label (Applied / OA / …)
   - `Date applied` = today or message date when status is Applied (do not overwrite a older applied date with a newer unrelated mail)
   - `Gmail thread` = URL
   - `Company`, `Role` from guesses when confident
5. Prefer status **upgrade** (Applied → OA → Interview …). Do not downgrade Interview to Applied.

## Prefer CLI when available

If the Mac has Notion env configured, you may instead run for the bulk path:

```bash
python -m jobradar gmail-sync --days 30
```

…then only MCP-fix rows that look wrong.

## Output

```json
{
  "upserted": [
    { "company": "", "role": "", "status": "Applied", "notion_page_id": "", "gmail_thread": "" }
  ],
  "created": 0,
  "updated": 0,
  "failed": []
}
```

Hand off to **04-verify-report**.
