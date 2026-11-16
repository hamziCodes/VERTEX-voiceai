#!/usr/bin/env bash
# Live certification steps (Phase 15, gate H15). NOTHING here runs unless
# Hamzi has approved that exact step and the operator exports
#   WAVIA_LIVE_APPROVED=<step id>
# Each step has a hard cap below; providers' own spend limits should also be
# set before running (see Codex Fix/evidence/phase-15/LIVE_CERTIFICATION_PLAN.md).
#
#   WAVIA_LIVE_APPROVED=L1 bash scripts/release/live_certification.sh L1
#   WAVIA_LIVE_APPROVED=L2 bash scripts/release/live_certification.sh L2
#
# L1  Provider reachability: read-only list/metadata calls, no generation.
# L2  Live pipeline: the release-image stack with live providers and the root
#     .env passed to Docker; at most L2_SESSIONS sessions of one text turn.
#
# Telephony (L4), AWS (L5), publishing (L6) and staging deploy (L7) are
# operator runbooks in the plan document, not automated here.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
STEP="${1:-}"
OUT="$ROOT/hamza_local/phase15/live/$STEP-$(date -u +%Y%m%dT%H%M%SZ)"
L2_SESSIONS="${L2_SESSIONS:-5}"
(( L2_SESSIONS <= 10 )) || { echo "L2_SESSIONS is capped at 10" >&2; exit 2; }

if [[ -z "$STEP" || "${WAVIA_LIVE_APPROVED:-}" != "$STEP" ]]; then
  echo "Refusing: step '$STEP' is not approved (set WAVIA_LIVE_APPROVED=$STEP only after Hamzi approves it)." >&2
  exit 3
fi
mkdir -p "$OUT"
if [[ -x .venv/Scripts/python.exe ]]; then VPY=.venv/Scripts/python.exe; else VPY=.venv/bin/python; fi

case "$STEP" in
  L1)
    "$VPY" scripts/ping_provider_apis.py | tee "$OUT/ping.log"
    ;;
  L2)
    [[ -f .env ]] || { echo "root .env with provider keys is required" >&2; exit 2; }
    export WAVIA_STACK_LIVE_PROVIDERS=1 WAVIA_STACK_ENV_FILE="$ROOT/.env"
    bash scripts/release/container_stack.sh run bash -c '
      set -e
      for i in $(seq 1 '"$L2_SESSIONS"'); do
        PYTHONPATH=sdk/python '"$VPY"' sdk/python/examples/quickstart.py \
          --control-plane http://127.0.0.1:28080 --ws-url ws://127.0.0.1:28081/ws/audio \
          --timeout 30 > "'"$OUT"'/session-$i.log" 2>&1 && echo "session $i: agent audio received" \
          || { echo "session $i: FAILED"; tail -3 "'"$OUT"'/session-$i.log"; }
      done
      docker logs wavia-qual-worker-raw > "'"$OUT"'/worker.log" 2>&1 || true
    ' | tee "$OUT/summary.log"
    ;;
  *)
    echo "unknown or non-automated step: $STEP" >&2
    exit 2
    ;;
esac
echo "evidence: $OUT"
