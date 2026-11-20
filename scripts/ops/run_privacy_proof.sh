#!/usr/bin/env bash
# Phase 14 privacy proof: disposable PostgreSQL + Adobe S3Mock (S3-compatible API),
# then tests/db/test_phase14_live_privacy.py. Nothing persists afterwards.
# boto3 comes from an ephemeral overlay (--with) so the project venv stays as locked.
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE=infra/docker/docker-compose.phase09-test.yml
export PHASE09_DB_PASSWORD="$(python -c 'import secrets;print(secrets.token_hex(16))')"
export AWS_ACCESS_KEY_ID="proof$(python -c 'import secrets;print(secrets.token_hex(6))')"
export AWS_SECRET_ACCESS_KEY="$(python -c 'import secrets;print(secrets.token_hex(20))')"
MINIO=wavia-privacy-s3
cleanup() {
  docker rm -f "$MINIO" >/dev/null 2>&1 || true
  docker compose -f "$COMPOSE" down --volumes >/dev/null 2>&1 || true
  echo "teardown: postgres=$(docker ps -a -q --filter name=phase09 | wc -l) minio=$(docker ps -a -q --filter name=$MINIO | wc -l)"
}
trap cleanup EXIT
docker compose -f "$COMPOSE" up -d --wait postgres >/dev/null
# MinIO no longer publishes pullable images; S3Mock implements the S3 calls
# the store uses (put/get/delete, list_objects_v2, delete_objects).
docker run -d --name "$MINIO" -p 127.0.0.1:59000:9090 adobe/s3mock:3.11.0 >/dev/null
for _ in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:59000/ && break; sleep 1; done
export DATABASE_URL="postgresql://phase09:${PHASE09_DB_PASSWORD}@127.0.0.1:55432/phase09"
export WAVIA_TEST_S3_ENDPOINT="http://127.0.0.1:59000"
export RUN_LIVE_DB_TESTS=1 UCVE_ENV=test RUN_LIVE_PROVIDERS=0 RUN_LIVE_TELEPHONY=0
python -m uv run --frozen --with boto3==1.43.118 --python 3.12 python -m pytest -q -p no:cacheprovider "${@:-tests/db/test_phase14_live_privacy.py}" 2>&1 | grep -v dev-dependencies | tail -40
