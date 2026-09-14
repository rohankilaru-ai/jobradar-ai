#!/usr/bin/env bash
# Safe DB refresh: backs up data/jobradar.db then recreates empty schema.
# Use after parser fixes to rewrite cross-wired SQLite rows cleanly.

set -euo pipefail

DB_PATH="${JOBRADAR_DB_PATH:-data/jobradar.db}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "No DB at $DB_PATH — nothing to backup."
  exit 1
fi

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_PATH="${DB_PATH}.backup_${TIMESTAMP}"

echo "Backing up: $DB_PATH → $BACKUP_PATH"
cp "$DB_PATH" "$BACKUP_PATH"

echo "Removing old DB: $DB_PATH"
rm "$DB_PATH"

echo "Recreating empty schema via Python..."
python -m jobradar db-init

echo "Done. Restore with: cp $BACKUP_PATH $DB_PATH"
