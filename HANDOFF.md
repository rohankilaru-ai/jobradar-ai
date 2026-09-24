# JobRadar-AI — Handoff for Cursor (post-MVP)

**Repo:** https://github.com/rohankilaru-ai/jobradar-ai  
**Local:** `/Users/rohankilaru/Resume Bot/job-agent-notifier/`  
**Branch:** `main`

## Latest: Overnight #54 — Stack Hygiene (PR #62 merged) — COMPLETE

**Goal:** Squash-merge green PR #62 (overnight #53 HANDOFF hygiene + drift-lock tests) onto main; refresh this handoff so Latest records the merge and Next stays post-MVP Rohan/Director ops only. Leave PR #23 untouched. No new feature work.

**Completed:**
- **PR #62 squash-merged** to main (`479fb48`) — Overnight #53 HANDOFF stack hygiene + 3 drift-lock tests (CI test checks SUCCESS before merge)
- **Local Mac checkout** fast-forwarded to `origin/main` at `479fb48`
- **CloudAgent** still usage-exhausted (on-demand needed); Mac path used for merge + this HANDOFF refresh
- **Pytest:** **723 passed** on Mac (`JOBRADAR_SKIP_DOTENV=1`) before this refresh; suite remains green after
- **PR #23 left untouched** (Gmail pack). No live Discord/ntfy/Telegram / no `scan --once` with alerts this cycle.
- **Product-complete signal: Yes** (unchanged; already on main via #61)

**Branch:** `overnight/54-handoff-hygiene` (HANDOFF refresh only)

**Next suggested:** Post-MVP priorities for Rohan/Director only — e.g. Grok Bot Director webhook URL when UI exposes it, cloud-scan GitHub Actions secrets, optional 24/7 scan ops. Do NOT invent overnight feature work. Do NOT re-suggest already-landed work (URL/alert-quality #41, product-completion tests #42, live-scan validation #43, product-complete review #45, PROJECT_SPEC SMS→Discord align #46 / PR #61, HANDOFF hygiene #53 / PR #62, classification recall, notify-window, classify-exclude, scout-health, parser HTML/URL harden #28). Leave PR #23 untouched. Skip all Gmail setup/Inbox wakes.

## Latest prior: Overnight #53 — Stack Hygiene (PR #61 merged) — COMPLETE

**Goal:** Stack hygiene after overnight #52 opened PR #61 for the overnight #46 lineage (#43+#45+#46). Squash-merge green PR #61 onto main; refresh this handoff so Next no longer says Mac push needed. Leave PR #23 untouched. No new feature work.

**Completed:**
- **PR #61 squash-merged** to main (`271d6ed`) — Overnight #43+#45+#46: Live-scan validation docs/harness + product-complete MVP review + PROJECT_SPEC Discord/ntfy/Telegram align → **product-complete Yes** (CI test checks SUCCESS before merge)
- **Local Mac checkout** fast-forwarded to `origin/main` at `271d6ed`
- **CloudAgent** still usage-exhausted (on-demand needed); Mac path used for merge + this HANDOFF refresh
- **PR #23 left untouched** (Gmail pack). No live Discord/ntfy/Telegram / no `scan --once` with alerts this cycle.
- **Product-complete signal: Yes** (unchanged; now on main)

**Branch:** `overnight/53-handoff-hygiene` (HANDOFF refresh only)

**Next suggested:** Post-MVP priorities for Rohan/Director only — e.g. Grok Bot Director webhook URL when UI exposes it, cloud-scan GitHub Actions secrets, optional 24/7 scan ops. Do NOT re-suggest already-landed work (URL/alert-quality #41, product-completion tests #42, live-scan validation #43, product-complete review #45, PROJECT_SPEC SMS→Discord align #46 / PR #61, classification recall, notify-window, classify-exclude, scout-health, parser HTML/URL harden #28). Leave PR #23 untouched. Skip all Gmail setup/Inbox wakes.

## Latest prior: Overnight #46 — Product Spec Align → Product-Complete Yes — COMPLETE (MERGED via PR #61)

**Goal:** Close the two material gaps from overnight #45 by amending `PROJECT_SPEC.md` to match the shipped product (Discord/ntfy/Telegram; New-Grad optional), refresh the product-complete review to **Yes**, and drift-lock with tests. Keep #43+#45 in the same lineage. Leave PR #23 untouched. Do **not** implement Twilio or re-enable New-Grad.

**Completed:**
- **PROJECT_SPEC.md:** SMS/Twilio removed as required alert channel; fast path / priorities / Grok Bots name Discord + ntfy + Telegram (+ JSONL mock); New-Grad marked optional / out of internship-MVP (disabled by default); SMS/Twilio listed under Out of MVP
- **Review:** `docs/PRODUCT_COMPLETE_REVIEW.md` — Product-complete signal **Yes**; SMS and New-Grad rows reclassified **met (spec-aligned)**; material gaps closed by #46 amendment note
- **Tests:** `tests/test_overnight_46_product_spec_align.py` (drift-locks for channels, no SMS/Twilio deliverable, New-Grad optional, review Yes); overnight #45 locks still pass
- **Lineage:** #43 + #45 + #46 on top of #42 / PR #60 / `1f8f463`
- **Pushed** by overnight #52 (Mac) as branch `overnight/46-product-spec-align` tip `9348610`; **PR #61** opened then squash-merged by overnight #53 → main `271d6ed`
- **Pytest at land:** **720 passed** (`JOBRADAR_SKIP_DOTENV=1`)
- **PR #23 left untouched** (Gmail pack). No live alerts.
- **Product-complete signal: Yes**

**Branch:** `overnight/46-product-spec-align` → squash-merged via PR #61

**Next suggested:** Superseded by overnight #53 stack hygiene (HANDOFF refresh). Do NOT re-suggest already-landed work listed above.

## Latest prior: Overnight #45 — Product-Complete MVP Review — PARTIAL (Mac push needed; superseded by #46 on same lineage)

**Goal:** Product-complete MVP review on top of overnight #43 tip: honest `docs/PRODUCT_COMPLETE_REVIEW.md` checklist + thin acceptance locks for PROJECT_SPEC claims prior suites missed. No push (same blockers as #43/#44). Leave PR #23 untouched.

**Completed:**
- **Review doc:** `docs/PRODUCT_COMPLETE_REVIEW.md` — maps fast path, sources, dedupe, classify, alerts, SQLite, CLI, Docker, out-of-MVP (Gmail skipped), slow path → met / partial / gap with evidence
- **Tests:** `tests/test_overnight_45_product_complete_review.py` (7 locks: Dockerfile/compose, SQLite tables, alert shape, MVP source catalog, CLI, Director 8s timeout)
- **Branch:** `overnight/45-product-complete-review` from #43 tip `c4b53f4` (lineage includes live-scan validation + #42 product-completion tests)
- **Pytest:** **715 passed** on box (`JOBRADAR_SKIP_DOTENV=1`)
- **Blocked:** box has no GitHub push creds; Mac offline; CloudAgent usage exhausted — branch not pushed / PR not opened
- **Artifacts for Mac resume:** `/workspace/overnight-45-product-complete-review.bundle`, `/workspace/0001-Overnight-45-Product-complete-review.patch`, `/workspace/MAC_FINISH_OVERNIGHT_45.sh` (applies #43+#45 lineage as one PR) — prefer `MAC_FINISH_OVERNIGHT_46.sh` once #46 is ready
- **PR #23 left untouched** (Gmail pack). No live Discord/ntfy/Telegram / no `scan --once` with alerts this cycle.
- **Product-complete signal: No** (at #45) — SMS/Twilio still absent vs literal PROJECT_SPEC; Simplify New-Grad source intentionally disabled. Closed by overnight #46 spec amend → Yes.

**Branch:** `overnight/45-product-complete-review` (local only until Mac push; contains #43 + #45; tip included in #46 lineage)

**Next suggested:** Superseded by overnight #46 — use `MAC_FINISH_OVERNIGHT_46.sh` for combined #43+#45+#46 push.

## Latest prior: Overnight #44 — Stack Hygiene — PARTIAL (Mac push needed for #43)


**Goal:** Merge open overnight PR #60 (product-completion tests) onto main, then land overnight #43 live-scan validation docs/harness on top. Leave PR #23 untouched.

**Completed:**
- **PR #60 squash-merged** to main (`1f8f463`) — Overnight #42 product-completion tests (CI was green)
- **Overnight #43 rebased** onto post-#60 main as commit `b14f487` on branch `overnight/43-live-scan-validation-docs`: conflict markers cleaned in `docs/LIVE_SCAN_VALIDATION.md`; docs/harness/drift-lock refresh; **708 pytest passed** on box
- **Blocked:** box has no GitHub push creds; Mac offline; CloudAgent usage exhausted — branch not pushed / PR not opened yet
- **Artifacts for Mac resume:** `/workspace/overnight-43-live-scan-validation.bundle`, `/workspace/0001-Overnight-43-Live-scan-validation-docs-harness-refre.patch`, `/workspace/MAC_FINISH_OVERNIGHT_43.sh`
- **PR #23 left untouched** (Gmail pack). No live Discord/ntfy/Telegram / no `scan --once` with alerts this cycle.

**Branch:** `overnight/43-live-scan-validation-docs` (local only until Mac push)

**Next suggested:** When Mac returns, run `MAC_FINISH_OVERNIGHT_43.sh` (or copy bundle/patch to `/tmp` and push + `gh pr create`), then merge #43. After that: product-complete review. Do NOT re-suggest already-landed feature work (URL/alert-quality harden #41, product-completion tests #42, live-scan validation docs #43, classification recall, notify-window, classify-exclude, scout-health, parser HTML/URL harden #28).

## Latest prior: Overnight #42 — Product-Completion / MVP Acceptance Tests — COMPLETE (MERGED)

**Goal:** End-to-end product acceptance / completion coverage (fast path without Grok, fixture/empty URL hard-block, 14-day store-vs-alert, priority tagging, recall-first, dedupe, health CLI, dotenv isolation).

**Status:** Squash-merged as PR #60 → main tip `1f8f463`. Dotenv isolation glue (`_load_env` / `JOBRADAR_SKIP_DOTENV` / conftest) is on main.


## Latest prior: Overnight #41 — URL/Alert-Quality Harden — COMPLETE

**Goal:** Tighten empty/placeholder/`example.com` (and similar fixture/dummy) URL gates end-to-end so bad/fixture URLs never reach Discord/ntfy/Telegram — including the company-name↔host match bypass beyond overnight #8/#9/#28.

**Completed:**
- **Shared fixture helper** `is_fixture_or_dummy_url` in `src/jobradar/models.py` (suffix-safe host match so `contest.com` ≠ `test.com`)
- **Notify gate** `job_notify_block_reason` now blocks all fixture/dummy hosts with `fixture/dummy URL: …` *before* domain-match / specificity checks (closes company=`Test` + `test.com` / `Example` + `example.net` / `Localhost` bypass)
- **`is_url_quality_good`** aligned to the shared helper; expanded `BAD_URL_PATTERNS` (`example.net`, `test.org`, `0.0.0.0`, …)
- **`probe_url`** short-circuits fixture hosts locally (no HTTP — `example.com` can return 200)
- **Parser ingest** still strips fixtures via `is_bad_url` → empty URL; regression covered
- **Tests:** `tests/test_url_alert_quality_harden.py` + probe mocks retargeted off fixture hosts; CLI smoke test no longer treats `example.com` as a "valid URL"
- **PR #23 left untouched** (Gmail pack). No live Discord/ntfy/Telegram sends this cycle.
- **Merged to main** as PR #59 (`10f9a3c`)

**Branch:** `overnight/41-url-alert-quality-harden`

## Latest prior: Overnight #39/#40 — Classification Recall + Stack Hygiene — COMPLETE

**Goal:** Land overnight #39 classification-recall feature (PR #57) and clear stack hygiene: close superseded PR #22; leave Gmail PR #23 untouched; refresh this handoff so Next no longer points at classification recall.

**Completed:**
- **PR #57 merged** ("Overnight #39: Classification recall for borderline technical roles") — squash-merged to main (`b2f9e9b`)
- **PR #22 closed** ("Remove Discord per-scan alert cap") — superseded by PR #40; commented + closed, not merged
- **PR #23 left open untouched** (Gmail/Notion inbox pack — Phase 4; standing skip)
- **Local Mac checkout** fast-forwarded to `origin/main` at `b2f9e9b`
- **Test suite at merge:** 643 tests passing (+11 classification-recall smokes)

**Branch:** `cursor/overnight-39-classification-recall-d530` (PR #57) → squash-merged to main (`b2f9e9b`)

**PR merged:**
- **PR #55** already on main (overnight #37 scout health) via overnight #38 hygiene
- **PR #57** ("Overnight #39: Classification recall…") — `strong_signals` overrides for Technical Account Manager / Technical Product Manager so exclude-list patterns do not drop borderline technical roles; 11 new tests in `tests/test_classify_dedupe_notify.py`

**Remaining open PRs:**
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).
- **PR #22** — CLOSED (superseded by #40).

**Main tip after this hygiene:** `b2f9e9b` (was `ca49f86` / HANDOFF #56 before #57).

**Next suggested:** URL/alert-quality harden — tighten empty/placeholder/`example.com` gates end-to-end (parser ingest + notify block reasons + regression tests) so bad/fixture URLs never reach Discord/ntfy/Telegram even when parsers or upstream HTML drift. Prefer test-driven gaps beyond overnight #8/#9/#28 already-landed coverage. Do NOT suggest already-landed work (classification recall, notify-window, classify-exclude, scout-health, parser HTML/URL harden #28).

## Latest prior: Overnight #38 — Merge/Stack Hygiene (PR #55) — COMPLETE

**Goal:** Merge/stack hygiene for overnight #37 draft PR #55 onto main. No new feature work. Mirror overnight #31/#34/#36 pattern.

**Completed:**
- **PR #55 merged** ("Overnight #37: Scout health age/staleness surfacing")
- **PR marked ready** for review (converted from draft)
- **Resolved HANDOFF.md merge conflict** after PR #54 landed (merged origin/main into PR branch, cleaned conflict markers)
- **Full pytest green** before merge (all 632 tests passing ✅)
- **Main tip after overnight #38:** 6ebf952 (was 42f5b51 before overnight #38)

**Branch:** `cursor/overnight-37-scout-health-staleness-96a2` (PR #55) → squash-merged to main (6ebf952)

**PR merged:**
- **PR #55** ("Overnight #37: Scout health age/staleness surfacing") — Added source health age/staleness observability to `health` CLI. Database enhancements for age calculation, staleness detection (3-day default threshold), fresh/stale classification. CLI shows stale sources and never-fetched sources. 10 new tests in test_scout_health.py. All 632 tests passing after merge.

**Remaining open PRs:**
- **PR #22** ("Remove Discord per-scan alert cap") — superseded by PR #40 (unlimited alert cap default). Leave for user to close.
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).


## Latest prior: Overnight #37 — Scout Health Age/Staleness Surfacing (PR #55) — LANDED

**Branch:** `cursor/overnight-37-scout-health-staleness-96a2` → squash-merged to main (6ebf952)

**Goal:** Add observability for source health **age** (time since last successful fetch) and **staleness** (sources not updated for >N days) in `python -m jobradar health` output so operators can spot dead/quiet sources without manual spot-checks. Build on overnight #33 / PR #51 scout_health foundation.

**Completed:**
- **Database enhancements** (`src/jobradar/db.py`): `SCOUT_HEALTH_STALENESS_THRESHOLD_DAYS = 3` constant, `get_scout_health_with_age()` method for age calculation, staleness detection, `_format_age()` helper
- **Health CLI enhancements** (`src/jobradar/cli.py`): Age/staleness summary, stale sources list, never-fetched sources list, preserved error display
- **Edge cases**: Only ok/not_modified count as fresh, never-fetched detection, threshold boundaries, empty history handling
- **Tests:** 10 new tests in `tests/test_scout_health.py` — fresh/stale/boundary/mixed/custom threshold/no history/age formatting/CLI display
- **All 632 tests passing** ✅

**Status:** Squash-merged to main (6ebf952) as part of overnight #38 stack hygiene.

## Latest prior: Overnight #36 — Merge/Stack Hygiene (PR #53/#54) — COMPLETE

**Goal:** Merge/stack hygiene for overnight #35 draft PR #53 onto main. No new feature work. Mirror overnight #31/#34 pattern.

**Completed:**
- **PR #53 merged** ("Overnight #35: Audit and normalize notify window docs drift")
- **PR #54 merged** (HANDOFF update after #53)
- **PR marked ready** for review (converted from draft)
- **Resolved merge conflict** in HANDOFF.md (merged main into PR branch, resolved cleanly)
- **CI green** before merge (test check SUCCESS)
- **Test suite:** All 622 tests passing ✅
- **Main tip after overnight #36:** 42f5b51 (was 8a84e86 before overnight #36)

**Branch:** `cursor/overnight-36-handoff-update-1cbe` (PR #54) → squash-merged to main (42f5b51)

**PR merged:**
- **PR #53** ("Overnight #35: Audit and normalize notify window docs drift (3-day → 14-day)") — Fixed docs/workflows to match canonical 14-day default, added 4 drift-lock tests, 622 tests passing after merge

**Remaining open PRs (at time of overnight #36 completion):**
- **PR #22** ("Remove Discord per-scan alert cap") — superseded by PR #40 (unlimited alert cap default). Leave for user to close.
- **PR #23** ("Local Mac inbox→Notion agent pack") — Gmail/Notion inbox pack (Phase 4). Left untouched per standing rules (skip all Gmail work).
