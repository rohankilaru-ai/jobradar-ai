#!/usr/bin/env bash
# Optional local scan loop (debug). Prefer GitHub Actions cloud-scan for Discord.
# Keep JOBRADAR_ALERTS_ENABLED=0 in .env when cloud-scan owns Discord.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
mkdir -p "$ROOT/data/logs"
exec python -m jobradar scan --loop --interval "${JOBRADAR_SCAN_INTERVAL_SEC:-300}"
