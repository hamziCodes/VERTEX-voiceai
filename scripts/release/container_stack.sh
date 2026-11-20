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
# Live providers only through scripts/release/live_certification.sh, which
# sets WAVIA_STACK_LIVE_PROVIDERS=1 and WAVIA_STACK_ENV_FILE after an explicit
# per-step approval. The env file is passed to Docker, never read here.
COMMON_ENV=()
if [[ -n "${WAVIA_STACK_ENV_FILE:-}" ]]; then
  # docker.exe on Windows cannot open a Git-Bash path (/d/...) once
  # MSYS_NO_PATHCONV=1 disables conversion, so hand it a native path.
  env_file="$WAVIA_STACK_ENV_FILE"
  if command -v cygpath >/dev/null 2>&1; then env_file="$(cygpath -w "$env_file")"; fi
  [[ -f "$WAVIA_STACK_ENV_FILE" ]] || { echo "WAVIA_STACK_ENV_FILE not found" >&2; exit 2; }
  COMMON_ENV+=(--env-file "$env_file")
fi
COMMON_ENV+=(
  -e UCVE_ENV=development -e UCVE_DEMO_MODE=1 -e UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES=1
  -e RUN_LIVE_PROVIDERS="${WAVIA_STACK_LIVE_PROVIDERS:-0}" -e RUN_LIVE_TELEPHONY=0
  -e DATABASE_URL="$DB_URL" -e REDIS_URL="redis://${PREFIX}-redis:6379/0"
  -e UCVE_WS_PUBLIC_URL="ws://127.0.0.1:28081/ws/audio"
  # Shared S3-compatible object storage (Adobe S3Mock) so the control plane,
  # worker and jobs runner see the same knowledge files and recordings, as
  # they would on S3. Dummy credentials; nothing leaves the Docker network.
  -e UCVE_KNOWLEDGE_S3_BUCKET=wavia-knowledge -e UCVE_KNOWLEDGE_S3_ENDPOINT="http://${PREFIX}-s3:9090"
  -e UCVE_RECORDING_S3_BUCKET=wavia-recordings -e UCVE_RECORDING_S3_ENDPOINT="http://${PREFIX}-s3:9090"
  -e UCVE_RECORDING_STORAGE_REGION=me-central-1 -e AWS_REGION=me-central-1 -e AWS_DEFAULT_REGION=me-central-1
  -e AWS_ACCESS_KEY_ID=qualification -e AWS_SECRET_ACCESS_KEY=qualification
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
  docker rm -f "${PREFIX}-idp" "${PREFIX}-control-plane" "${PREFIX}-worker-raw" "${PREFIX}-worker-jobs" \
    "${PREFIX}-telephony-gateway" "${PREFIX}-postgres" "${PREFIX}-redis" "${PREFIX}-s3" >/dev/null 2>&1 || true
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
  docker run -d --name "${PREFIX}-s3" --network "$NET"     -e initialBuckets=wavia-knowledge,wavia-recordings adobe/s3mock:3.11.0 >/dev/null
  until docker exec "${PREFIX}-postgres" pg_isready -U wavia -d wavia >/dev/null 2>&1; do sleep 1; done
  sleep 2  # the image restarts postgres once after initdb
  until docker exec "${PREFIX}-postgres" pg_isready -U wavia -d wavia >/dev/null 2>&1; do sleep 1; done
  echo "== migrations (control-plane image)"
  docker run --rm --network "$NET" "wavia-control-plane:$TAG" \
    python -m infra.db.migrate --database-url "$DB_URL" | tail -c 300; echo
  local cp_extra=()
  if [[ "${WAVIA_STACK_IDP:-0}" == "1" ]]; then
    # Offline identity provider for the customer-journey checkup: Studio's own
    # WorkOS test double, run as a sidecar in the control plane's network so
    # both Studio (host) and the control plane see it at 127.0.0.1:3211, the
    # only plain-HTTP JWKS origin the control plane accepts. Identity is the
    # only external service doubled; the control plane, worker and database
    # are the release images.
    cp_extra=(-p 127.0.0.1:3211:3211
      -e OIDC_ISSUER=http://127.0.0.1:3211/ -e OIDC_JWKS_URL=http://127.0.0.1:3211/jwks
      -e OIDC_AUDIENCE=client_offline_test -e UCVE_ALLOWED_ORIGINS=http://127.0.0.1:3100
      -e UCVE_DEMO_MODE=0)  # the journey must not rely on unauthenticated demo mints
  fi
  service control-plane 8080 "${cp_extra[@]}"
  if [[ "${WAVIA_STACK_IDP:-0}" == "1" ]]; then
    local fixture; fixture="$(cygpath -w "$PWD/studio/e2e/fixtures" 2>/dev/null || echo "$PWD/studio/e2e/fixtures")"
    MSYS_NO_PATHCONV=1 docker run -d --name "${PREFIX}-idp" --network "container:${PREFIX}-control-plane" \
      -v "${fixture}:/fixtures:ro" -e WAVIA_E2E_FIXTURE_BIND=0.0.0.0 -e WAVIA_E2E_FIXTURE_PORT=3211 \
      -e WAVIA_E2E_APP_PORT=3100 node:22-alpine node /fixtures/offline-auth-server.mjs >/dev/null
    wait_ready idp http://127.0.0.1:3211/health 60
  fi
  local worker_extra=()
  if [[ "${WAVIA_STACK_IDP:-0}" == "1" && "${WAVIA_STACK_LIVE_PROVIDERS:-0}" != "1" ]]; then
    # Studio's "mock" voice test signs a fixed-mock-transcript constraint;
    # the worker must run in that mode (real VAD, mock STT/LLM/TTS).
    worker_extra=(-e "UCVE_STT_MOCK_TEXT=What are your opening hours?")
  fi
  service worker-raw 8081 "${worker_extra[@]}"
  service worker-jobs 8084
  # A throwaway Ed25519 public key (the gateway rejects malformed keys at
  # startup); no Telnyx account is involved.
  local telnyx_key="${TELNYX_PUBLIC_KEY:-$(docker run --rm "wavia-control-plane:$TAG" python -c \
    'import base64;from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as K;from cryptography.hazmat.primitives import serialization as s;print(base64.b64encode(K.generate().public_key().public_bytes(s.Encoding.Raw,s.PublicFormat.Raw)).decode())')}"
  service telephony-gateway 8083 -e TELNYX_PUBLIC_KEY="$telnyx_key"
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
