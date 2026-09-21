# JobRadar-AI — Project Spec

Personal internship radar for Rohan (UC Berkeley Data Science).
Targets: SWE, DS, DE, ML, AI research, quant, infra, applied AI.

## Priorities

1. **Notification speed** — never block alerts on Grok Bots, LLM calls, or missing API keys.
2. False positives OK. Missed jobs not OK.
3. No auto-apply. No email alerts. Python owns SMS/Discord (mock JSONL until keys exist).

## Architecture

### Fast path (never blocked)

GitHub sources → normalize → rule dedupe → rule classify → SQLite → SMS + Discord
(mock → `data/notifications.jsonl` until Twilio/Discord keys exist).

### Slow path (best-effort)

After persist + notify, POST compact `JobRecord` JSON to Director / Analyst / Resume Mapper
webhooks if env vars exist. Timeout 8s. Never raise into the notify path. Empty webhook = skip.

## Sources (MVP)

JSON first:

- `aprameyak/2027-tech-jobs` → `listings.json`
- `dreamworkhq/Tech-Internships-2027` → `data/listings.json`
- `ApplyGuy/2027-Internships` → `data/internships.json`

Markdown tables (`raw.githubusercontent.com`, ETag cache):

- `SimplifyJobs/Summer2027-Internships` (`dev`) — `README.md`, `README-Off-Season.md` (skip Inactive)
- `SimplifyJobs/New-Grad-Positions` (`dev`)
- `vanshb03/Summer2027-Internships` (`dev`) — handle `↳` inherit company
- `speedyapply/2027-SWE-College-Jobs` (`main`) — `README.md`, `INTERN_INTL.md`

**Do not scrape** `pittcsc/Summer2027-Internships` (stale Simplify fork).

Backfill 14 days for notify; older rows still stored.

## Dedupe

- Same `canonical_key` → merge
- Else same company AND title similarity ≥ 80 AND location similarity ≥ 80 (rapidfuzz) → prefer merge

## Classify

- Include keywords → keep
- Exclude (tax, nursing, …) → drop
- Else keep (recall-first)

## Alert format

```
{Company}
{Role} | {Location}
{Source} | {Link}

{two-line summary}
```

Priority companies get `[PRIORITY]`. Cooldown 0. Never notify twice.

Priority companies: OpenAI, Anthropic, Databricks, Snowflake, Nvidia, Scale AI, Perplexity,
Meta, Google, Microsoft, Apple, Tesla, Palantir, Stripe, Figma, Roblox, Netflix,
Jane Street, Hudson River Trading, Citadel, Ramp, Cursor, Anduril, xAI.

## SQLite

Tables: `jobs`, `job_sources`, `notifications`, `agent_runs`, `fetch_cache`;
empty stubs: `emails`, `applications`. Unique on `canonical_key`.

## CLI

```
python -m jobradar scan --once
python -m jobradar scan --loop --interval 300
python -m jobradar health
python -m jobradar ping-grok
```

## Docker

`python:3.12-slim`, volume `./data`.

## Out of MVP

Auto-apply, heavy frontend, career-page HTML scrape, newsletters, Gmail, awesome-job-boards crawl,
`github.com/topics/job-board`.

## Grok Bots

Run on Rohan's Mac. Missing bots must not stop SMS/Discord. Specs live in `agents/grok/`.
