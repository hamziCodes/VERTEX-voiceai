#!/usr/bin/env bash
# Phase 15 release drills against the release images (disposable, offline,
# mock providers). Each drill prints PASS/FAIL lines; the script exits 1 if
# any drill failed. Evidence goes to hamza_local/phase15/drills/.
#
#   bash scripts/release/drills.sh [upgrade rollback redis restart network]
#
# upgrade   previous-release schema (migrations 001-033) with data, upgraded
#           by the new control-plane image; data, ledger and checksums kept.
# rollback  previous release's code (PREVIOUS_RELEASE, default b087147) run on
#           the new image's runtime against the upgraded schema.
# redis     Redis restart under the running stack; readiness and a real SDK
#           session afterwards.
# restart   worker and control plane killed (SIGKILL) and restarted.
# network   PostgreSQL disconnected from the network: readiness must fail
#           and mint must fail fast and cleanly; then recovery.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
TAG="${WAVIA_TAG:-p15}"
PREVIOUS_RELEASE="${PREVIOUS_RELEASE:-b087147}"
OUT="$ROOT/hamza_local/phase15/drills"
mkdir -p "$OUT"
STACK="bash scripts/release/container_stack.sh"
P=wavia-qual
CP=http://127.0.0.1:28080
WS=ws://127.0.0.1:28081/ws/audio
if [[ -x .venv/Scripts/python.exe ]]; then VPY=.venv/Scripts/python.exe; else VPY=.venv/bin/python; fi
FAILED=0
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; FAILED=1; }
psql_q() { docker exec "$P-postgres" psql -U wavia -d wavia -tAc "$1"; }
session_ok() {  # a real SDK session: mint, connect, text turn, agent audio
  PYTHONPATH=sdk/python "$VPY" sdk/python/examples/quickstart.py \
    --control-plane "$CP" --ws-url "$WS" --timeout 20 >"$OUT/session-$1.log" 2>&1
}
ready() { curl -s -o /dev/null -w '%{http_code}' "$1/health/ready"; }
wait_status() {  # url expected seconds
  local start; start=$(date +%s)
  while [[ "$(ready "$1")" != "$2" ]]; do
    (( $(date +%s) - start > $3 )) && return 1
    sleep 1
  done
  echo $(( $(date +%s) - start ))
}

drill_upgrade() {
  echo "== drill: upgrade from the previous release schema"
  local prev="$OUT/migrations-001-033"
  rm -rf "$prev" && mkdir -p "$prev"
  git archive "$PREVIOUS_RELEASE" infra/db/migrations | tar -x -C "$OUT" --strip-components=0
  cp "$OUT"/infra/db/migrations/*.sql "$prev"/ && rm -rf "$OUT/infra"
  echo "previous release $PREVIOUS_RELEASE has $(ls "$prev" | wc -l) migrations"
  $STACK down
  docker network create "$P" >/dev/null 2>&1 || true
  docker network create wavia-qual >/dev/null 2>&1 || true
  local pw; pw=$(python -c 'import secrets;print(secrets.token_hex(16))')
  MSYS_NO_PATHCONV=1 docker run -d --name "$P-postgres" --network wavia-qual \
    --tmpfs /var/lib/postgresql/data -e POSTGRES_DB=wavia -e POSTGRES_USER=wavia \
    -e POSTGRES_PASSWORD="$pw" pgvector/pgvector:pg16 >/dev/null
  until docker exec "$P-postgres" pg_isready -U wavia -d wavia >/dev/null 2>&1; do sleep 1; done
  sleep 2
  until docker exec "$P-postgres" pg_isready -U wavia -d wavia >/dev/null 2>&1; do sleep 1; done
  local url="postgresql://wavia:${pw}@$P-postgres:5432/wavia"
  local mount; mount="$(cygpath -w "$prev" 2>/dev/null || echo "$prev")"
  MSYS_NO_PATHCONV=1 docker run --rm --network wavia-qual -v "${mount}:/app/infra/db/migrations:ro" \
    "wavia-control-plane:$TAG" python -m infra.db.migrate --database-url "$url" >"$OUT/upgrade-old.log" 2>&1 \
    || { fail "upgrade: previous-release migrations"; tail "$OUT/upgrade-old.log"; return; }
  psql_q "INSERT INTO tenants (id, name) VALUES ('11111111-1111-1111-1111-111111111111', 'drill tenant');
          INSERT INTO agents (id, tenant_id, name) VALUES ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', 'drill agent');" >/dev/null
  local before; before=$(psql_q "SELECT count(*), string_agg(filename||':'||checksum_sha256, ',' ORDER BY filename) FROM schema_migrations")
  MSYS_NO_PATHCONV=1 docker run --rm --network wavia-qual "wavia-control-plane:$TAG" \
    python -m infra.db.migrate --database-url "$url" >"$OUT/upgrade-new.log" 2>&1 \
    || { fail "upgrade: new migrations"; tail "$OUT/upgrade-new.log"; return; }
  echo "upgrade applied: $(tail -c 200 "$OUT/upgrade-new.log")"
  local after_count; after_count=$(psql_q "SELECT count(*) FROM schema_migrations")
  local kept; kept=$(psql_q "SELECT count(*) FROM schema_migrations WHERE filename < '034'")
  local old_ledger; old_ledger=$(psql_q "SELECT count(*), string_agg(filename||':'||checksum_sha256, ',' ORDER BY filename) FROM schema_migrations WHERE filename < '034'")
  local data; data=$(psql_q "SELECT (SELECT count(*) FROM tenants WHERE id='11111111-1111-1111-1111-111111111111') || '/' || (SELECT count(*) FROM agents WHERE id='22222222-2222-2222-2222-222222222222')")
  local again; again=$(MSYS_NO_PATHCONV=1 docker run --rm --network wavia-qual "wavia-control-plane:$TAG" python -m infra.db.migrate --database-url "$url" 2>&1)
  [[ "$before" == "$old_ledger" ]] && pass "upgrade: previous ledger unchanged ($kept entries, checksums equal)" || fail "upgrade: previous ledger changed"
  [[ "$after_count" == "36" ]] && pass "upgrade: ledger now 36 migrations" || fail "upgrade: ledger has $after_count"
  [[ "$data" == "1/1" ]] && pass "upgrade: pre-upgrade rows kept" || fail "upgrade: rows $data"
  [[ "$again" == *"no pending"* ]] && pass "upgrade: re-run finds nothing pending" || fail "upgrade: re-run: $again"
  echo "$url" > "$OUT/.upgrade-url"
}

drill_rollback() {
  echo "== drill: previous release code ($PREVIOUS_RELEASE) on the upgraded schema"
  [[ -f "$OUT/.upgrade-url" ]] || drill_upgrade
  local url; url=$(cat "$OUT/.upgrade-url")
  local src="$OUT/previous-src"
  rm -rf "$src" && mkdir -p "$src"
  git archive "$PREVIOUS_RELEASE" core control_plane post_call telephony_gateway worker_raw infra examples/web-client openapi.yaml | tar -x -C "$src"
  local mount; mount="$(cygpath -w "$src" 2>/dev/null || echo "$src")"
  docker rm -f "$P-rollback-cp" >/dev/null 2>&1
  MSYS_NO_PATHCONV=1 docker run -d --name "$P-rollback-cp" --network wavia-qual -p 127.0.0.1:28090:8080 \
    -v "${mount}:/src:ro" -w /src -e PYTHONPATH=/src \
    -e UCVE_ENV=development -e UCVE_DEMO_MODE=1 -e UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES=1 \
    -e DATABASE_URL="$url" "wavia-control-plane:$TAG" \
    uvicorn control_plane.app:app --host 0.0.0.0 --port 8080 >/dev/null
  local t
  if t=$(wait_status http://127.0.0.1:28090 200 60); then
    pass "rollback: previous control plane ready on the new schema in ${t}s"
  else
    fail "rollback: previous control plane not ready"; docker logs --tail 30 "$P-rollback-cp"
  fi
  local code; code=$(curl -s -o "$OUT/rollback-mint.json" -w '%{http_code}' -X POST http://127.0.0.1:28090/v1/session/mint \
    -H 'Content-Type: application/json' \
    -d '{"tenant_id":"11111111-1111-1111-1111-111111111111","agent_id":"22222222-2222-2222-2222-222222222222"}')
  [[ "$code" == "200" ]] && pass "rollback: previous code mints against upgraded data" || fail "rollback: mint HTTP $code"
  docker logs "$P-rollback-cp" >"$OUT/rollback-cp.log" 2>&1
  docker rm -f "$P-rollback-cp" "$P-postgres" >/dev/null 2>&1
  rm -f "$OUT/.upgrade-url"
}

drill_redis() {
  echo "== drill: Redis restart"
  $STACK up >"$OUT/stack-redis.log" 2>&1 || { fail "redis: stack up"; return; }
  session_ok redis-before && pass "redis: session before restart" || fail "redis: session before restart"
  docker restart "$P-redis" >/dev/null
  local t
  t=$(wait_status "$CP" 200 30) && pass "redis: control plane ready ${t}s after Redis restart" || fail "redis: control plane not ready"
  t=$(wait_status http://127.0.0.1:28081 200 30) && pass "redis: worker ready ${t}s after Redis restart" || fail "redis: worker not ready"
  session_ok redis-after && pass "redis: real session after restart" || { fail "redis: session after restart"; tail -5 "$OUT/session-redis-after.log"; }
}

drill_restart() {
  echo "== drill: worker and control plane SIGKILL + restart"
  [[ "$(ready "$CP")" == "200" ]] || $STACK up >"$OUT/stack-restart.log" 2>&1
  for svc in worker-raw control-plane; do
    docker kill "$P-$svc" >/dev/null && docker start "$P-$svc" >/dev/null
  done
  local t
  t=$(wait_status http://127.0.0.1:28081 200 60) && pass "restart: worker ready ${t}s after SIGKILL" || fail "restart: worker not ready"
  t=$(wait_status "$CP" 200 60) && pass "restart: control plane ready ${t}s after SIGKILL" || fail "restart: control plane not ready"
  session_ok restart && pass "restart: real session after restart" || { fail "restart: session after restart"; tail -5 "$OUT/session-restart.log"; }
}

drill_network() {
  echo "== drill: database network failure"
  [[ "$(ready "$CP")" == "200" ]] || $STACK up >"$OUT/stack-network.log" 2>&1
  docker network disconnect wavia-qual "$P-postgres"
  local t
  t=$(wait_status "$CP" 503 30) && pass "network: control plane reports not ready ${t}s after losing the database" || fail "network: control plane still ready"
  local start code
  start=$(date +%s)
  code=$(curl -s -m 60 -o "$OUT/network-mint.json" -w '%{http_code}' -X POST "$CP/v1/session/mint" -H 'Content-Type: application/json' \
    -d '{"tenant_id":"00000000-0000-0000-0000-000000000001","agent_id":"00000000-0000-0000-0000-0000000000a1"}')
  local took=$(( $(date +%s) - start ))
  echo "mint during outage: HTTP $code in ${took}s: $(head -c 200 "$OUT/network-mint.json")"
  [[ "$code" == "503" && $took -le 10 ]] && pass "network: mint fails fast with 503" || fail "network: mint returned HTTP $code after ${took}s"
  docker network connect wavia-qual "$P-postgres"
  t=$(wait_status "$CP" 200 60) && pass "network: control plane ready ${t}s after the database returned" || fail "network: no recovery"
  session_ok network && pass "network: real session after recovery" || { fail "network: session after recovery"; tail -5 "$OUT/session-network.log"; }
}

DRILLS=("$@")
[[ ${#DRILLS[@]} -eq 0 ]] && DRILLS=(upgrade rollback redis restart network)
for d in "${DRILLS[@]}"; do "drill_$d"; done
$STACK down
exit $FAILED
