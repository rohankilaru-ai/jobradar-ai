#!/usr/bin/env bash
# Local scan loop (LaunchAgent). Prefer ./scripts/scan-mode.sh local|cloud to flip Discord owner.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
mkdir -p "$ROOT/data/logs"
exec python -m jobradar scan --loop --interval "${JOBRADAR_SCAN_INTERVAL_SEC:-300}"
