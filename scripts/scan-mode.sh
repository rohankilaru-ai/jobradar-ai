#!/usr/bin/env bash
# Flip Discord scan between Mac (local) and GitHub Actions (cloud).
# Never run both Discord-on at once — separate DBs cause duplicate alerts.
#
# Usage:
#   ./scripts/scan-mode.sh status
#   ./scripts/scan-mode.sh local    # Mac LaunchAgent on, cloud-scan workflow off
#   ./scripts/scan-mode.sh cloud    # cloud-scan on, Mac LaunchAgent off
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.rohankilaru.jobradar-scan"
PLIST_SRC="$ROOT/config/launchd/com.rohankilaru.jobradar-scan.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PLIST_DISABLED="${PLIST_DST}.disabled"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

die() { echo "error: $*" >&2; exit 1; }

need_gh() {
  command -v gh >/dev/null 2>&1 || die "gh CLI required (brew install gh && gh auth login)"
}

set_env_alerts() {
  local value="$1"
  local envf="$ROOT/.env"
  [[ -f "$envf" ]] || die "missing $envf"
  if grep -q '^JOBRADAR_ALERTS_ENABLED=' "$envf"; then
    # portable in-place edit
    python3 - "$envf" "$value" <<'PY'
from pathlib import Path
import sys
path, val = Path(sys.argv[1]), sys.argv[2]
lines = []
for line in path.read_text().splitlines():
    if line.startswith("JOBRADAR_ALERTS_ENABLED="):
        lines.append(f"JOBRADAR_ALERTS_ENABLED={val}")
    else:
        lines.append(line)
path.write_text("\n".join(lines) + "\n")
PY
  else
    printf '\nJOBRADAR_ALERTS_ENABLED=%s\n' "$value" >> "$envf"
  fi
  echo "  .env JOBRADAR_ALERTS_ENABLED=${value}"
}

local_running() {
  launchctl print "${DOMAIN}/${LABEL}" 2>/dev/null | grep -q 'state = running' && return 0
  pgrep -f 'jobradar scan --loop' >/dev/null 2>&1
}

stop_local() {
  if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
    launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
  fi
  # Leave a disabled copy so login does not revive it
  if [[ -f "$PLIST_DST" ]]; then
    mv -f "$PLIST_DST" "$PLIST_DISABLED"
  fi
  # Kill stray loop if any
  if pgrep -f 'jobradar scan --loop' >/dev/null 2>&1; then
    pkill -f 'jobradar scan --loop' 2>/dev/null || true
  fi
  echo "  local LaunchAgent: stopped"
}

start_local() {
  [[ -f "$PLIST_SRC" ]] || die "missing plist template: $PLIST_SRC"
  mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/data/logs"
  # Prefer repo template (paths stay correct)
  cp -f "$PLIST_SRC" "$PLIST_DST"
  rm -f "$PLIST_DISABLED"
  # Replace if already loaded
  if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
    launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
  fi
  launchctl bootstrap "$DOMAIN" "$PLIST_DST"
  launchctl enable "${DOMAIN}/${LABEL}" 2>/dev/null || true
  launchctl kickstart -k "${DOMAIN}/${LABEL}" 2>/dev/null || true
  sleep 1
  if local_running; then
    echo "  local LaunchAgent: running"
  else
    die "local LaunchAgent failed to start — check data/logs/scan-loop-launchd.err.log"
  fi
}

cloud_enabled() {
  need_gh
  # "active" vs "disabled_*"
  local state
  state="$(gh workflow list --json name,state -q '.[] | select(.name=="cloud-scan") | .state' 2>/dev/null || true)"
  [[ "$state" == "active" ]]
}

disable_cloud() {
  need_gh
  if cloud_enabled; then
    gh workflow disable cloud-scan.yml
    echo "  cloud-scan workflow: disabled"
  else
    echo "  cloud-scan workflow: already disabled"
  fi
}

enable_cloud() {
  need_gh
  if cloud_enabled; then
    echo "  cloud-scan workflow: already active"
  else
    gh workflow enable cloud-scan.yml
    echo "  cloud-scan workflow: enabled"
  fi
}

cmd_status() {
  echo "JobRadar scan mode"
  echo
  if local_running; then
    echo "  local:  ON  (LaunchAgent / scan --loop)"
  else
    echo "  local:  OFF"
  fi
  if [[ -f "$ROOT/.env" ]] && grep -q '^JOBRADAR_ALERTS_ENABLED=0' "$ROOT/.env"; then
    echo "  Mac Discord alerts: OFF (JOBRADAR_ALERTS_ENABLED=0)"
  else
    echo "  Mac Discord alerts: ON  (JOBRADAR_ALERTS_ENABLED≠0 or unset→1)"
  fi
  if command -v gh >/dev/null 2>&1; then
    if cloud_enabled; then
      echo "  cloud:  ON  (workflow active)"
    else
      echo "  cloud:  OFF (workflow disabled)"
    fi
  else
    echo "  cloud:  ? (install gh to query)"
  fi
  echo
  echo "Flip:  ./scripts/scan-mode.sh local | cloud"
}

cmd_local() {
  echo "Switching to LOCAL mode (Mac Discord on, cloud off)…"
  disable_cloud
  set_env_alerts 1
  start_local
  echo
  echo "Done. Laptop must stay awake for Discord. Flip back: ./scripts/scan-mode.sh cloud"
  cmd_status
}

cmd_cloud() {
  echo "Switching to CLOUD mode (GitHub Discord on, Mac off)…"
  stop_local
  set_env_alerts 0
  enable_cloud
  echo
  echo "Done. Cron may lag; manual: gh workflow run cloud-scan.yml -f test_discord=true"
  echo "Flip back: ./scripts/scan-mode.sh local"
  cmd_status
}

case "${1:-status}" in
  status|s) cmd_status ;;
  local|mac|laptop) cmd_local ;;
  cloud|github|gha) cmd_cloud ;;
  -h|--help|help)
    sed -n '2,12p' "$0"
    ;;
  *)
    die "unknown mode '$1' — use: status | local | cloud"
    ;;
esac
