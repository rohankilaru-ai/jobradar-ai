# Subagent 02 — Gmail label

**Parent:** `agents/local/ORCHESTRATOR.md`  
**Input:** JSON from `01-gmail-discover`  
**Tools:** Gmail MCP (`list_labels`, `create_label`, `label_thread`, `unlabel_thread` / `update_message_labels` as available)

## Mission

Apply nested JobRadar labels to every candidate with `action` in `new` or `upgrade`. Leave `skip` and `uncertain` alone.

## Ensure labels exist

Create if missing (nested with `/`):

- `JobRadar`
- `JobRadar/Applied`
- `JobRadar/Waiting`
- `JobRadar/OA`
- `JobRadar/Interview`
- `JobRadar/Final Round`
- `JobRadar/Offer`
- `JobRadar/Rejected`
- `JobRadar/Ghosted`
- `JobRadar/Recruiter`
- `JobRadar/Backlog`

## Per thread

1. Add parent **`JobRadar`**.
2. Add exactly one nested status from `suggested_status`.
3. Remove any **other** `JobRadar/*` status labels on that thread (forward-only).
4. If legacy flat labels exist (`Applied`, `OA`, `Interview`, `Offer`, `Rejected`, `Waiting`, `Ghosted`, `Recruiter`, `Final Round`, `Job Oriented`, `Backlog` at root), remove them after the nested ones are set.

## Do not

- Label `uncertain` or `skip` rows
- Apply more than one nested status
- Trash, spam, archive, or mark read unless the user asked

## Output

```json
{
  "labeled": [
    { "thread_id": "", "status": "Applied", "company_guess": "", "subject": "" }
  ],
  "failed": [],
  "skipped": [],
  "counts": { "labeled": 0, "failed": 0, "skipped": 0 }
}
```

Hand off to **03-notion-upsert** (include full labeled list).
