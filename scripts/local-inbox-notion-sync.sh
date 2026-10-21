#!/usr/bin/env bash
# Local Gmail label + Notion status refresh (Mac).
# Usage:
#   ./scripts/local-inbox-notion-sync.sh           # 30 day reorganize + 14 day sync
#   ./scripts/local-inbox-notion-sync.sh 14
#   ./scripts/local-inbox-notion-sync.sh 30 --dry-run
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DAYS="${1:-30}"
shift || true
EXTRA=("${@:-}")

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

echo "== health =="
python -m jobradar health

if [[ " ${EXTRA[*]} " == *" --dry-run "* ]]; then
  echo "== gmail-reorganize dry-run days=${DAYS} =="
  python -m jobradar gmail-reorganize --days "$DAYS" --dry-run
  echo "dry-run only; re-run without --dry-run to apply"
  exit 0
fi

echo "== gmail-reorganize days=${DAYS} =="
python -m jobradar gmail-reorganize --days "$DAYS"

SYNC_DAYS="$DAYS"
if [[ "$DAYS" -gt 14 ]]; then
  SYNC_DAYS=14
fi
echo "== gmail-sync days=${SYNC_DAYS} =="
python -m jobradar gmail-sync --days "$SYNC_DAYS"

echo "== weekly-report =="
python -m jobradar weekly-report || true

echo "done. Spot-check Gmail label:JobRadar and Notion Tracker Status."
echo "Optional Cursor verify: @agents/local/subagents/04-verify-report.md"
