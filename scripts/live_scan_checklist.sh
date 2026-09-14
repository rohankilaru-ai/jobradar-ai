#!/usr/bin/env bash
# Live scan validation checklist — runs offline tests then health check
# No Discord sends, no secrets required for basic validation
set -e

echo "=== JobRadar Live Scan Validation ==="
echo

echo "[1/3] Running offline tests..."
pytest -v tests/test_live_scan.py
echo "✅ Offline tests passed"
echo

echo "[2/3] Running all tests..."
pytest -v
echo "✅ All tests passed"
echo

echo "[3/3] Health check..."
python -m jobradar health
echo "✅ Health check complete"
echo

echo "=== Validation Complete ==="
echo
echo "Next steps:"
echo "  - Run: python -m jobradar scan --once"
echo "  - Check: data/notifications.jsonl"
echo "  - Validate: Discord/ntfy if configured"
echo
echo "See docs/LIVE_SCAN_VALIDATION.md for full guide"
