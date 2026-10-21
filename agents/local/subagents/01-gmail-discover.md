# Subagent 01 — Gmail discover (new applications)

**Parent:** `agents/local/ORCHESTRATOR.md`  
**Tools:** Gmail MCP (`search_threads`, `get_thread`, `list_labels`) — read-only. Do **not** label yet.

## Mission

Find job-application threads from roughly the **last 14–30 days** that need (or need upgrading of) `JobRadar/*` labels.

## Search queries (run several)

```
newer_than:30d (subject:("thank you for applying" OR "application received" OR "application submitted" OR "we received your application" OR "application sent"))
newer_than:30d (from:(noreply OR no-reply OR careers OR recruiting) subject:(application OR applied))
newer_than:30d (subject:(hackerrank OR codesignal OR "online assessment" OR "coding assessment"))
newer_than:30d (subject:(interview OR "phone screen" OR "next steps") -subject:gradescope)
newer_than:30d (subject:(unfortunately OR "not moving forward" OR "other candidates" OR "will not be moving"))
newer_than:30d label:JobRadar
```

## For each candidate thread

Record:

| field | notes |
|---|---|
| `thread_id` | Gmail thread id |
| `subject` | first useful subject |
| `from` | sender |
| `company_guess` | best effort; empty if unsure |
| `role_guess` | best effort; empty if unsure |
| `suggested_status` | one of Applied / Waiting / OA / Interview / Final Round / Offer / Rejected / Ghosted / Recruiter / Backlog |
| `already_labeled` | current `JobRadar/*` labels if any |
| `action` | `new` \| `upgrade` \| `skip` \| `uncertain` |
| `skip_reason` | if skip (marketing / course / etc.) |

## Classification hints

- “Application sent” / “thank you for applying” → **Applied**
- “under review” / “in our database” → **Waiting**
- HackerRank / CodeSignal / OA invite → **OA**
- Interview / phone screen scheduled → **Interview**
- Superday / onsite / final → **Final Round**
- Offer → **Offer**
- Reject / not moving forward → **Rejected**
- Role closed / filled → **Ghosted**
- Inbound recruiter without prior apply → **Recruiter**
- Ambiguous job-ish → **uncertain** (do not label in 02)

## Skip list

Gradescope, Canvas, course staff, Handshake *digest/recommendation* blasts (keep Handshake *Application sent*), newsletters, LinkedIn “jobs you may like”.

## Output

Return JSON only:

```json
{
  "lookback_days": 30,
  "candidates": [ /* rows above */ ],
  "counts": { "new": 0, "upgrade": 0, "skip": 0, "uncertain": 0 }
}
```

Hand off to **02-gmail-label**.
