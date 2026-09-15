# JobRadar-AI

Personal internship radar for Rohan (UC Berkeley Data Science).

Scout GitHub internship lists → dedupe → classify → SQLite → notify (Discord / free ntfy phone push / Telegram).
Grok Bots analyze after notify; they never block alerts.

## Quick start

```bash
cd "/Users/rohankilaru/Resume Bot/job-agent-notifier"
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest
python -m jobradar health
python -m jobradar scan --once
```

## Docs

- [docs/ACCOUNTS.md](docs/ACCOUNTS.md) — Discord, Twilio, Notion, Gmail setup
- [docs/CLOUD_SCAN.md](docs/CLOUD_SCAN.md) — **24/7 scan with laptop closed** (GitHub Actions)
- [PROJECT_SPEC.md](PROJECT_SPEC.md) — product + architecture
- [UPLOAD_TO_GROK_BOT.md](UPLOAD_TO_GROK_BOT.md) — Director + sub-bot setup
- [docs/GROK_BOT_SETUP.md](docs/GROK_BOT_SETUP.md) — human click path
- [CURSOR_MASTER_PROMPT.md](CURSOR_MASTER_PROMPT.md) — coding standing orders
- Specs: [agents/grok/](agents/grok/)

## CLI

```
python -m jobradar scan --once
python -m jobradar scan --loop --interval 300
python -m jobradar health
python -m jobradar test-discord
python -m jobradar test-ntfy
python -m jobradar test-telegram
python -m jobradar test-notion
python -m jobradar notion-backfill --priority-only
python -m jobradar gmail-auth
python -m jobradar gmail-sync
python -m jobradar ping-grok
```

Prefer **cloud-scan** (GitHub Actions) over a local `--loop` so alerts keep working when your computer is asleep.

## Layout

```
src/jobradar/   Python package
tests/          pytest
data/           SQLite + notification JSONL (gitignored contents)
agents/grok/    Grok Bot specs
config/ prompts/ tasks/ docs/
```

Parent Resume Bot gitignores this tree; this folder has its own git repo.
