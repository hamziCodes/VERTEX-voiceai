#!/usr/bin/env bash
# Disposable local stack built only from the release images: PostgreSQL
# (pgvector, tmpfs), Redis, migrations, control plane, raw worker, jobs runner
# and telephony gateway on a private Docker network. Development mode, mock
# providers, no live provider or carrier, nothing published.
#
#   bash scripts/release/container_stack.sh up      # start and wait for ready
#   bash scripts/release/container_stack.sh down    # remove everything
#   bash scripts/release/container_stack.sh run CMD # up, run CMD, then down
#
# Images are expected as wavia-<service>:${WAVIA_TAG:-p15}. Host ports:
# control plane 28080, worker 28081, telephony 28083, jobs 28084.
set -euo pipefail

TAG="${WAVIA_TAG:-p15}"
NET="wavia-qual"
PREFIX="wavia-qual"
DB_PASSWORD="${WAVIA_QUAL_DB_PASSWORD:-$(python -c 'import secrets;print(secrets.token_hex(16))')}"
export WAVIA_QUAL_DB_PASSWORD="$DB_PASSWORD"
DB_URL="postgresql://wavia:${DB_PASSWORD}@${PREFIX}-postgres:5432/wavia"
COMMON_ENV=(
  -e UCVE_ENV=development -e UCVE_DEMO_MODE=1 -e UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES=1
  -e RUN_LIVE_PROVIDERS=0 -e RUN_LIVE_TELEPHONY=0
  -e DATABASE_URL="$DB_URL" -e REDIS_URL="redis://${PREFIX}-redis:6379/0"
  -e UCVE_WS_PUBLIC_URL="ws://127.0.0.1:28081/ws/audio"
)

wait_ready() {  # name url seconds
  local name=$1 url=$2 limit=${3:-60} start
  start=$(date +%s)
  until curl -sf "$url" >/dev/null 2>&1; do
    if (( $(date +%s) - start > limit )); then
      echo "$name not ready after ${limit}s"; docker logs --tail 40 "${PREFIX}-$name" 2>&1; return 1
    fi
    sleep 1
  done
  echo "$name ready in $(( $(date +%s) - start ))s"
}

down() {
  docker rm -f "${PREFIX}-control-plane" "${PREFIX}-worker-raw" "${PREFIX}-worker-jobs" \
    "${PREFIX}-telephony-gateway" "${PREFIX}-postgres" "${PREFIX}-redis" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}

service() {  # name port extra-args...
  local name=$1 port=$2; shift 2
  docker run -d --name "${PREFIX}-$name" --network "$NET" -p "127.0.0.1:2${port: -4}:$port" \
    "${COMMON_ENV[@]}" "$@" "wavia-$name:$TAG" >/dev/null
}

up() {
  down
  docker network create "$NET" >/dev/null
  # MSYS_NO_PATHCONV: Git Bash on Windows would rewrite the container path.
  MSYS_NO_PATHCONV=1 docker run -d --name "${PREFIX}-postgres" --network "$NET" \
    --tmpfs /var/lib/postgresql/data \
    -e POSTGRES_DB=wavia -e POSTGRES_USER=wavia -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    pgvector/pgvector:pg16 >/dev/null
  docker run -d --name "${PREFIX}-redis" --network "$NET" redis:7-alpine >/dev/null
  until docker exec "${PREFIX}-postgres" pg_isready -U wavia -d wavia >/dev/null 2>&1; do sleep 1; done
  sleep 2  # the image restarts postgres once after initdb
  until docker exec "${PREFIX}-postgres" pg_isready -U wavia -d wavia >/dev/null 2>&1; do sleep 1; done
  echo "== migrations (control-plane image)"
  docker run --rm --network "$NET" "wavia-control-plane:$TAG" \
    python -m infra.db.migrate --database-url "$DB_URL" | tail -c 300; echo
  service control-plane 8080
  service worker-raw 8081
  service worker-jobs 8084
  service telephony-gateway 8083 -e TELNYX_PUBLIC_KEY="${TELNYX_PUBLIC_KEY:-qualification-placeholder}"
  wait_ready control-plane http://127.0.0.1:28080/health/ready
  wait_ready worker-raw http://127.0.0.1:28081/health/ready
  wait_ready worker-jobs http://127.0.0.1:28084/health/ready
  wait_ready telephony-gateway http://127.0.0.1:28083/health/ready || echo "telephony-gateway: see readiness detail above"
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  run) shift; trap down EXIT; up; "$@" ;;
  *) echo "usage: $0 up|down|run CMD..." >&2; exit 2 ;;
esac
