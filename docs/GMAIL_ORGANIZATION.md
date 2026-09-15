# Gmail organization for job applications

Single source of truth for how JobRadar labels recruiting mail.

## Design principles

1. **One parent, one status** — every job thread gets `JobRadar` plus exactly one nested status label.
2. **Progress is forward-only in the UI** — when a thread advances (Applied → OA → Interview), the old status label is removed automatically.
3. **Nested only** — flat labels (`Applied`, `OA`, …) and `Job Oriented` are legacy; hidden and stripped on sync.
4. **Notion mirrors status** — Gmail status maps 1:1 to Notion `Status` on the JobRadar Tracker board.

## Label hierarchy

```
JobRadar/                 ← parent (every job thread)
├── Applied               ← application confirmation
├── Waiting               ← under review / in database
├── OA                    ← online assessment invite
├── Interview             ← phone screen / interview scheduled
├── Final Round           ← onsite / superday
├── Offer
├── Rejected
├── Ghosted               ← role closed / filled
├── Recruiter             ← inbound recruiter outreach
└── Backlog               ← misc job mail (optional)
```

## Status progression

When newer mail in a thread indicates a later stage, the **highest** stage wins:

```
Applied < Waiting < Recruiter < OA < Interview < Final Round < Offer
Rejected and Ghosted override when detected
```

## Gmail sidebar (recommended order)

Drag nested labels under `JobRadar` in this order:

Applied → Waiting → OA → Interview → Final Round → Offer → Rejected → Ghosted → Recruiter → Backlog

Colors are set in code (`ensure_labels`); Gmail MCP can adjust presets if you want.

## Commands

```bash
# Incremental (last 7 days) — runs in cloud-scan too
python -m jobradar gmail-sync --days 7

# One-time backfill / cleanup (local OAuth)
python -m jobradar gmail-reorganize --days 365
python -m jobradar gmail-reorganize --days 365 --dry-run   # preview only
```

## What cloud-scan does

When `GMAIL_CLIENT_SECRETS_JSON` + `GMAIL_TOKEN_JSON` GitHub secrets are set, every 30 min:

1. `scan --once` — new internship listings → Discord/Notion
2. `gmail-sync` — classify recent mail → nested labels + Notion status

Your Mac can stay closed.

## Live backfill (done)

A full pass labeled real application mail under `JobRadar/*` (ATS confirmations, Handshake "Application sent", rejections, OA/Interview). Marketing Handshake digests and Gradescope/course mail were left unlabeled on purpose.

Refresh in Gmail: click **JobRadar** in the left sidebar (or search `label:JobRadar`). New mail is picked up by `gmail-sync` once cloud-scan secrets are set.

## Filters (optional, manual)

Gmail MCP cannot create filters on this account (403). Create these in Gmail → Settings → Filters if you want instant labeling on arrival:

| Filter query | Apply label |
|---|---|
| `subject:(thank you for applying OR application received)` | `JobRadar/Applied` |
| `subject:(hackerrank OR codesignal OR online assessment)` | `JobRadar/OA` |
| `subject:(interview OR phone screen)` | `JobRadar/Interview` |
| `subject:(unfortunately OR not moving forward)` | `JobRadar/Rejected` |

Always also apply parent `JobRadar`. Skip inbox optional.
