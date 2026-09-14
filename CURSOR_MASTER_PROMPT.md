# Cursor Master Prompt — JobRadar-AI

You are implementing JobRadar-AI in `job-agent-notifier/`.

Rules:

1. TDD. Frequent commits. Co-author: `Co-Authored-By: Cursor Grok 4.6 <noreply@cursor.com>`
2. Fast path never waits on Grok Bots or missing keys.
3. Work only in this folder except parent `tools/grok-bot/` and `resumes/master.md`.
4. Never dump giant GitHub READMEs into prompts — pass compact JobRecord only.
5. Ask before email/Slack/Gmail/account changes.
6. Do not wrap unofficial Grok Bot gateway port 1340.
7. HTTP 200 from a Grok webhook means the run **started**, not finished.
8. Read `PROJECT_SPEC.md` and `UPLOAD_TO_GROK_BOT.md` before coding.

Implementation order:

1. Spec package + git skeleton + `.env.example` ← current
2. JobRecord + sqlite (unique canonical_key)
3. Parsers: markdown tables + JSON fixtures
4. Scout + ETag cache; per-source failures isolated
5. Dedupe + classify rules
6. Notifier mocks → `data/notifications.jsonl`
7. Pipeline CLI + Docker + GitHub Actions pytest
8. Director webhook client (skip if no keys) + `agents/grok/*.spec.md`
9. JSON logs + health
10. Document Gmail/VM in docs — do not implement
