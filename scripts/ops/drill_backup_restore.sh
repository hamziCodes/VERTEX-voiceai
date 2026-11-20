#!/usr/bin/env bash
# Backup/restore drill against a disposable PostgreSQL (Phase 14).
#
# Proves that a logical backup (pg_dump -Fc) of a fully migrated database with
# data restores into an empty database with identical migration ledger
# (filenames + SHA-256 checksums), row counts for every table, row-level
# security flags and policies, and that the migration runner then finds
# nothing pending. It never touches a shared or production database.
#
#   bash scripts/ops/drill_backup_restore.sh
#
# Production uses the hosting provider's snapshots/PITR in addition (H14);
# this drill covers the portable logical path and the restore verification.
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE=infra/docker/docker-compose.phase09-test.yml
export PHASE09_DB_PASSWORD="$(python -c 'import secrets;print(secrets.token_hex(16))')"
PY="python -m uv run --frozen --python 3.12 python"
cleanup() { docker compose -f "$COMPOSE" down --volumes >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker compose -f "$COMPOSE" up -d --wait postgres >/dev/null
CONTAINER="$(docker compose -f "$COMPOSE" ps -q postgres)"
SRC="postgresql://phase09:${PHASE09_DB_PASSWORD}@127.0.0.1:55432/phase09"
DST="postgresql://phase09:${PHASE09_DB_PASSWORD}@127.0.0.1:55432/restored"

$PY scripts/ops/db_fingerprint.py migrate "$SRC"
$PY scripts/ops/db_fingerprint.py seed "$SRC"
WORK="${WAVIA_DRILL_DIR:-hamza_local/drills}"
mkdir -p "$WORK"
BEFORE="$WORK/db-before.json"
AFTER="$WORK/db-after.json"
$PY scripts/ops/db_fingerprint.py fingerprint "$SRC" > "$BEFORE"

t0=$(date +%s)
docker exec "$CONTAINER" pg_dump -U phase09 -d phase09 -Fc -f /tmp/wavia.dump
SIZE=$(docker exec "$CONTAINER" stat -c %s /tmp/wavia.dump)
docker exec "$CONTAINER" createdb -U phase09 restored
docker exec "$CONTAINER" pg_restore -U phase09 -d restored --exit-on-error /tmp/wavia.dump
t1=$(date +%s)

$PY scripts/ops/db_fingerprint.py fingerprint "$DST" > "$AFTER"
$PY scripts/ops/db_fingerprint.py compare "$BEFORE" "$AFTER"
$PY scripts/ops/db_fingerprint.py migrate "$DST"
echo "backup bytes: $SIZE; dump+restore seconds: $((t1 - t0))"
