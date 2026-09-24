# Product-Complete MVP Review (Overnight #45)

Honest checklist mapping `PROJECT_SPEC.md` MVP requirements to evidence.
Status values: **met** | **partial** | **gap** | **out-of-MVP (skipped)**.

**Review base:** branch `overnight/45-product-complete-review` on tip including overnight #43 (`c4b53f4`) + #42 product-completion tests (PR #60).  
**Date:** 2026-09-24 (PT).  
**Product-complete signal:** **No** — see Material gaps. Core fast-path MVP is largely implemented and acceptance-tested; two intentional/spec-drift items remain.

---

## Summary

| Area | Status |
|------|--------|
| Fast path (never blocked by Grok) | met |
| Sources (JSON + Markdown catalog) | partial |
| Dedupe | met |
| Classify (recall-first) | met |
| Alerts (format, priority, idempotent, mock) | partial |
| SQLite schema | met |
| CLI (`scan` / `health` / `ping-grok`) | met |
| Docker | met |
| Out-of-MVP boundaries (incl. Gmail) | met (skipped) |
| Slow path (Director webhooks) | met |

---

## 1. Fast path (never blocked)

**Spec:** GitHub sources → normalize → rule dedupe → rule classify → SQLite → SMS + Discord (mock JSONL until keys). Never block on Grok/LLM/missing keys.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| End-to-end scout→classify→dedupe→persist→notify without Grok | **met** | `tests/test_overnight_42_product_completion.py::test_fast_path_scan_classify_dedupe_persist_notify_without_grok`; `tests/test_product_completion.py` offline scan | — |
| Director/Notion errors do not crash notify | **met** | `tests/test_overnight_29_product_completion.py::test_pipeline_resilience_director_error`, `…_notion_error` | — |
| Empty webhook / missing keys → skip | **met** | `test_product_completion.py::test_empty_notification_keys_skip_gracefully`; `test_product.py::test_adapters_skip_without_keys` | — |
| Seed mode: first populate does not alert storm | **met** | `test_product_completion.py::test_scan_once_offline_path`; classify/dedupe pipeline empty-sources tests | — |

---

## 2. Sources (MVP)

**Spec JSON:** `aprameyak/2027-tech-jobs`, `dreamworkhq/Tech-Internships-2027`, `ApplyGuy/2027-Internships`.  
**Spec Markdown:** Simplify Summer + Off-Season, Simplify New-Grad, vanshb03, speedyapply SWE + AI (README + INTERN_INTL; NEW_GRAD_* excluded).  
**Ban:** do not scrape `pittcsc/Summer2027-Internships`. Backfill 14 days for notify; older still stored.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Core JSON + internship MD sources present | **met** | `src/jobradar/sources.py` SOURCES; `tests/test_sources_policy.py`; overnight #45 catalog lock | — |
| speedyapply AI intern sources (not NEW_GRAD_*) | **met** | `test_sources_policy.py::test_speedyapply_ai_*` | — |
| pittcsc banned | **met** | `test_sources_policy.py`, `test_live_scan.py`, harness drift-lock | — |
| `SimplifyJobs/New-Grad-Positions` | **partial** | Commented out in `sources.py` (“internships only”); locked by `test_newgrad_sources_disabled` | Literal PROJECT_SPEC lists New-Grad; product intentionally disables it |
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
| Discord / ntfy / Telegram + JSONL mock | **met** | `notify.py` adapters; product-completion suites | — |
| **SMS / Twilio** | **partial / gap** | No Twilio/SMS adapter in codebase | Spec still says “SMS + Discord”; product evolved to Discord/ntfy/Telegram + JSONL. Material vs literal spec; not blocking Discord/ntfy path |
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

**Spec out-of-MVP:** auto-apply, heavy frontend, career-page HTML scrape, newsletters, **Gmail**, awesome-job-boards crawl, `github.com/topics/job-board`.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Phase 4 Gmail not required for MVP | **out-of-MVP (skipped)** | Standing skip; PR #23 left untouched; no Gmail work this cycle | Do not treat open PR #23 as MVP blocker |
| No auto-apply | **met** | No auto-apply path in pipeline | — |
| pittcsc not scraped | **met** | sources policy tests | — |

---

## 10. Slow path (best-effort)

**Spec:** After persist+notify, POST compact JobRecord to Director/Analyst/Resume Mapper if env set. Timeout 8s. Never raise into notify. Empty = skip.

| Claim | Status | Evidence | Gap |
|-------|--------|----------|-----|
| Timeout 8s / enqueue best-effort | **met** | `director.py` `timeout=8.0`; resilience tests | — |
| Missing env skips | **met** | ping-grok / enqueue empty | — |

---

## Material gaps (honest)

1. **SMS/Twilio absent** — PROJECT_SPEC still names SMS; implementation is Discord/ntfy/Telegram + JSONL mock. Treat as **spec drift / partial**, not a Discord-path blocker. Closing it means either implement Twilio or update PROJECT_SPEC.
2. **Simplify New-Grad source disabled** — listed in PROJECT_SPEC sources, intentionally commented out for internships-only. **Intentional partial**; do not re-enable without product decision.

No other material MVP implementation gaps found for the fast path, dedupe, classify, SQLite, CLI, Docker, or alert quality gates under current product interpretation.

---

## Acceptance / test map (primary)

- `tests/test_overnight_42_product_completion.py` — MVP acceptance suite (#42 / PR #60)
- `tests/test_product_completion.py` — offline scan / notify product suite
- `tests/test_overnight_29_product_completion.py` — quality-gate stack integration
- `tests/test_product.py` — thin DB/adapter smokes
- `tests/test_overnight_45_product_complete_review.py` — review locks (Docker, schema tables, alert shape, MVP source catalog, CLI)
- `docs/LIVE_SCAN_VALIDATION.md` — operator live/offline validation (#43)

## Verdict

**Product-complete signal: No.**  
Fast-path MVP is substantially complete and heavily tested, but the review will not claim “product-complete” while SMS remains a literal PROJECT_SPEC deliverable and New-Grad remains a listed-but-disabled source without an explicit PROJECT_SPEC amendment.
