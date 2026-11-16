#!/usr/bin/env bash
# Run the database- and Redis-backed tests against disposable containers
# (compose file infra/docker/docker-compose.phase09-test.yml: pgvector
# PostgreSQL on 127.0.0.1:55432, Redis on 56379, tmpfs only), then remove
# them and print what is left. Never points at a shared database.
#
#   bash scripts/release/run_live_db_tests.sh [pytest targets...]
#   (default: tests/db tests/hardening/test_h3_persistence.py tests/metering/test_phase09_live_redis.py)
set -u
cd "$(dirname "$0")/../.."
COMPOSE=infra/docker/docker-compose.phase09-test.yml
export PHASE09_DB_PASSWORD="$(python -c 'import secrets;print(secrets.token_hex(16))')"
cleanup() {
  docker compose -f "$COMPOSE" down --volumes >/dev/null 2>&1
  echo "--- after teardown ---"
  echo "containers: $(docker ps -a --filter name=phase09 -q | wc -l)"
  echo "volumes: $(docker volume ls -q | grep -c phase09)"
}
trap cleanup EXIT
docker compose -f "$COMPOSE" up -d --wait postgres redis >/dev/null 2>&1 || { echo "compose up failed"; exit 1; }
export DATABASE_URL="postgresql://phase09:${PHASE09_DB_PASSWORD}@127.0.0.1:55432/phase09"
export REDIS_URL="redis://127.0.0.1:56379/0"
export RUN_LIVE_DB_TESTS=1 RUN_LIVE_REDIS_TESTS=1 UCVE_ENV=test RUN_LIVE_PROVIDERS=0 RUN_LIVE_TELEPHONY=0
if [[ $# -eq 0 ]]; then
  set -- tests/db tests/hardening/test_h3_persistence.py tests/metering/test_phase09_live_redis.py
fi
python -m uv run --frozen --python 3.12 python -m pytest -q -p no:cacheprovider "$@" 2>&1 | tail -40
