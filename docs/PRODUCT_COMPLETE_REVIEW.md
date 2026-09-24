# Product-Complete MVP Review (Overnight #45 + #46)

Honest checklist mapping `PROJECT_SPEC.md` MVP requirements to evidence.
Status values: **met** | **partial** | **gap** | **out-of-MVP (skipped)**.

**Review base:** branch `overnight/46-product-spec-align` tip (lineage: overnight #43 live-scan docs + #45 product-complete review + #46 PROJECT_SPEC align, on top of #42 / PR #60).  
**Date:** 2026-09-24 (PT).  
**Product-complete signal:** **Yes** — overnight #46 amended `PROJECT_SPEC.md` so literal requirements match the shipped product (Discord/ntfy/Telegram + optional New-Grad). No Twilio implementation; New-Grad left disabled.

---

## Summary

| Area | Status |
|------|--------|
| Fast path (never blocked by Grok) | met |
| Sources (JSON + Markdown catalog) | met |
| Dedupe | met |
| Classify (recall-first) | met |
| Alerts (format, priority, idempotent, mock) | met |
| SQLite schema | met |
| CLI (`scan` / `health` / `ping-grok`) | met |
| Docker | met |
| Out-of-MVP boundaries (incl. Gmail) | met (skipped) |
| Slow path (Director webhooks) | met |

---

## 1. Fast path (never blocked)

**Spec:** GitHub sources → normalize → rule dedupe → rule classify → SQLite → Discord + ntfy + Telegram (mock JSONL until keys). Never block on Grok/LLM/missing keys.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| End-to-end scout→classify→dedupe→persist→notify without Grok | **met** | `tests/test_overnight_42_product_completion.py::test_fast_path_scan_classify_dedupe_persist_notify_without_grok`; `tests/test_product_completion.py` offline scan | — |
| Director/Notion errors do not crash notify | **met** | `tests/test_overnight_29_product_completion.py::test_pipeline_resilience_director_error`, `…_notion_error` | — |
| Empty webhook / missing keys → skip | **met** | `test_product_completion.py::test_empty_notification_keys_skip_gracefully`; `test_product.py::test_adapters_skip_without_keys` | — |
| Seed mode: first populate does not alert storm | **met** | `test_product_completion.py::test_scan_once_offline_path`; classify/dedupe pipeline empty-sources tests | — |

---

## 2. Sources (MVP)

**Spec JSON:** `aprameyak/2027-tech-jobs`, `dreamworkhq/Tech-Internships-2027`, `ApplyGuy/2027-Internships`.  
**Spec Markdown (required):** Simplify Summer + Off-Season, vanshb03, speedyapply SWE + AI (README + INTERN_INTL; NEW_GRAD_* excluded).  
**Optional / out of internship-MVP:** `SimplifyJobs/New-Grad-Positions` — disabled by default; not a required MVP source (#46 PROJECT_SPEC amendment).  
**Ban:** do not scrape `pittcsc/Summer2027-Internships`. Backfill 14 days for notify; older still stored.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Core JSON + internship MD sources present | **met** | `src/jobradar/sources.py` SOURCES; `tests/test_sources_policy.py`; overnight #45 catalog lock | — |
| speedyapply AI intern sources (not NEW_GRAD_*) | **met** | `test_sources_policy.py::test_speedyapply_ai_*` | — |
| pittcsc banned | **met** | `test_sources_policy.py`, `test_live_scan.py`, harness drift-lock | — |
| `SimplifyJobs/New-Grad-Positions` | **met** (spec-aligned optional) | Commented out in `sources.py` (“internships only”); locked by `test_newgrad_sources_disabled`; PROJECT_SPEC (#46) marks optional / out of internship-MVP | — |
| 14-day notify / older stored | **met** | `NOTIFY_WINDOW_DAYS==14`; `test_overnight_42…::test_fourteen_day_window_old_stored_not_alerted`; notify-window drift-lock tests | — |
| ETag / fetch_cache | **met** | `fetch_cache` table + scout cache tests (`tests/test_scout.py`) | — |

---

## 3. Dedupe

**Spec:** same `canonical_key` → merge; else same company AND title≥80 AND location≥80 (rapidfuzz) → prefer merge.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| canonical_key uniqueness / merge | **met** | DB `PRIMARY KEY`; upsert tests; overnight #42 e2e | — |
| Fuzzy threshold 80 | **met** | `dedupe.py` default `threshold=80.0`; `test_classify_dedupe_notify.py`; `test_overnight_42…::test_dedupe_merges_near_duplicates` | — |

---

## 4. Classify

**Spec:** include → keep; exclude (tax, nursing, …) → drop; else keep (recall-first). False positives OK.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Recall-first / ambiguous kept | **met** | `test_overnight_42…::test_recall_first_classify_keeps_ambiguous`; `test_product_completion.py::test_classify_keeps_ambiguous_jobs` | — |
| Hard excludes (nursing, new-grad-only, …) | **met** | overnight #29/#39/#42 classify tests; TAM/TPM strong-signal recall (#39) | — |

---

## 5. Alerts

**Spec format:**
```
{Company}
{Role} | {Location}
{Source} | {Link}

{two-line summary}
```
Priority → `[PRIORITY]`. Cooldown 0. Never notify twice. Mock → `data/notifications.jsonl` until keys.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Alert text shape + `[PRIORITY]` | **met** | `notify.format_alert`; overnight #45 shape lock; overnight #42 priority acceptance | — |
| Priority company list | **met** | `classify.PRIORITY_COMPANIES` matches PROJECT_SPEC (24 names) | — |
| Never notify twice (idempotent) | **met** | `notifications.canonical_key` unique; `test_product_completion.py::test_notify_idempotency_*` | — |
| Bad/empty/fixture URLs never alert | **met** | overnight #41/#42 URL gates; `job_notify_block_reason` | — |
| Discord / ntfy / Telegram + JSONL mock | **met** | `notify.py` adapters; product-completion suites; PROJECT_SPEC (#46) names these channels | — |
| SMS / Twilio | **met** (spec-aligned out-of-MVP) | Not a deliverable; PROJECT_SPEC (#46) lists SMS/Twilio under Out of MVP; phone push is ntfy/Telegram | — |
| Cooldown 0 | **met** | No cooldown delay; idempotency via `was_notified` only | — |

---

## 6. SQLite

**Spec tables:** `jobs`, `job_sources`, `notifications`, `agent_runs`, `fetch_cache`; empty stubs `emails`, `applications`. Unique on `canonical_key`.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Required tables exist | **met** | `db.SCHEMA`; overnight #45 schema lock; `test_db_refresh.py` | — |
| jobs.canonical_key unique | **met** | `PRIMARY KEY` | — |

---

## 7. CLI

**Spec:** `scan --once`, `scan --loop --interval 300`, `health`, `ping-grok`.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Commands registered | **met** | `cli.build_parser`; smoke + overnight #45 CLI lock; `test_product_completion.py` flag validation | — |
| `health` offline smoke | **met** | `test_overnight_42…::test_health_cli_smoke`; `test_health_cli.py`; scout staleness (#37) | — |
| `validate-scan` harness (extra) | **met** | overnight #43 docs + harness tests | beyond MVP, helpful |

---

## 8. Docker

**Spec:** `python:3.12-slim`, volume `./data`.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Base image + VOLUME | **met** | `Dockerfile`; overnight #45 Docker lock | — |
| Compose mounts `./data` | **met** | `docker-compose.yml`; overnight #45 lock | — |

---

## 9. Out of MVP / boundaries

**Spec out-of-MVP:** auto-apply, heavy frontend, career-page HTML scrape, newsletters, **Gmail**, awesome-job-boards crawl, `github.com/topics/job-board`, SMS/Twilio.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Phase 4 Gmail not required for MVP | **out-of-MVP (skipped)** | Standing skip; PR #23 left untouched; no Gmail work this cycle | Do not treat open PR #23 as MVP blocker |
| No auto-apply | **met** | No auto-apply path in pipeline | — |
| pittcsc not scraped | **met** | sources policy tests | — |
| SMS/Twilio not required | **met** | PROJECT_SPEC (#46) Out of MVP; ntfy/Telegram for phone push | — |

---

## 10. Slow path (best-effort)

**Spec:** After persist+notify, POST compact JobRecord to Director/Analyst/Resume Mapper if env set. Timeout 8s. Never raise into notify. Empty = skip.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Timeout 8s / enqueue best-effort | **met** | `director.py` `timeout=8.0`; resilience tests | — |
| Missing env skips | **met** | ping-grok / enqueue empty | — |

---

## Material gaps (honest)

**None remaining for MVP.** Overnight #46 closed the two #45 material gaps by amending PROJECT_SPEC (not by implementing Twilio or re-enabling New-Grad):

1. ~~SMS/Twilio absent~~ → **resolved (spec-aligned):** PROJECT_SPEC now requires Discord + ntfy + Telegram (+ JSONL mock); SMS/Twilio is Out of MVP.
2. ~~Simplify New-Grad source disabled~~ → **resolved (spec-aligned):** PROJECT_SPEC marks New-Grad optional / out of internship-MVP; product correctly leaves it disabled.

No other material MVP implementation gaps found for the fast path, dedupe, classify, SQLite, CLI, Docker, or alert quality gates.

---

## Acceptance / test map (primary)

- `tests/test_overnight_42_product_completion.py` — MVP acceptance suite (#42 / PR #60)
- `tests/test_product_completion.py` — offline scan / notify product suite
- `tests/test_overnight_29_product_completion.py` — quality-gate stack integration
- `tests/test_product.py` — thin DB/adapter smokes
- `tests/test_overnight_45_product_complete_review.py` — review locks (Docker, schema tables, alert shape, MVP source catalog, CLI)
- `tests/test_overnight_46_product_spec_align.py` — PROJECT_SPEC drift-locks (no SMS/Twilio deliverable; New-Grad optional; Discord/ntfy/Telegram named)
- `docs/LIVE_SCAN_VALIDATION.md` — operator live/offline validation (#43)

## Verdict

**Product-complete signal: Yes.**  
Fast-path MVP matches amended PROJECT_SPEC (#46). Discord/ntfy/Telegram + JSONL mock are the alert channels; New-Grad is optional/out-of-internship-MVP and remains disabled. Gmail (PR #23) stays out-of-MVP / untouched.
