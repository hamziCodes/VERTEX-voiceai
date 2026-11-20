#!/usr/bin/env bash
# Build the Python and TypeScript SDK packages, install each into an isolated
# consumer project, and run its quickstart against a running engine (by
# default the release-image stack from container_stack.sh: development demo
# mode, mock providers). No provider, carrier or registry is contacted.
#
#   bash scripts/release/container_stack.sh run bash scripts/release/qualify_sdks.sh
#
# Artifacts and logs land in hamza_local/phase15/sdk/ (gitignored).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/hamza_local/phase15/sdk"
CP_URL="${CP_URL:-http://127.0.0.1:28080}"
WS_URL="${WS_URL:-ws://127.0.0.1:28081/ws/audio}"
rm -rf "$OUT" && mkdir -p "$OUT/dist" "$OUT/py-consumer" "$OUT/ts-consumer"
cd "$ROOT"

UV=(uv)
command -v uv >/dev/null 2>&1 || UV=(python -m uv)

echo "== build Python SDK (wheel + sdist)"
"${UV[@]}" build sdk/python --out-dir "$OUT/dist" >"$OUT/py-build.log" 2>&1
ls "$OUT/dist"

echo "== build TypeScript SDK (npm pack)"
( cd sdk/typescript && npm ci --no-audit --no-fund >"$OUT/ts-ci.log" 2>&1 \
  && npm run build >"$OUT/ts-build.log" 2>&1 \
  && npm test >"$OUT/ts-test.log" 2>&1 \
  && npm pack --pack-destination "$OUT/dist" >"$OUT/ts-pack.log" 2>&1 )
ls "$OUT/dist"

echo "== engine: $CP_URL (control plane), $WS_URL (worker)"
curl -sf "$CP_URL/health/ready" >/dev/null || { echo "control plane not ready at $CP_URL"; exit 1; }

echo "== Python consumer: fresh venv, install the wheel only"
python -m venv "$OUT/py-consumer/venv"
if [[ -x "$OUT/py-consumer/venv/Scripts/python.exe" ]]; then CPY="$OUT/py-consumer/venv/Scripts/python.exe"; else CPY="$OUT/py-consumer/venv/bin/python"; fi
"$CPY" -m pip install --quiet "$OUT"/dist/ucve_voice_sdk-*.whl
cp sdk/python/examples/quickstart.py "$OUT/py-consumer/"
( cd "$OUT/py-consumer" && "$CPY" -I quickstart.py \
    --control-plane "$CP_URL" --ws-url "$WS_URL" ) | tee "$OUT/py-quickstart.log"

echo "== TypeScript consumer: fresh project, install the tarball only"
cp sdk/typescript/examples/quickstart.mjs "$OUT/ts-consumer/"
( cd "$OUT/ts-consumer" && npm init -y >/dev/null \
  && npm install --no-audit --no-fund "$OUT"/dist/ucve-voice-sdk-*.tgz >"$OUT/ts-install.log" 2>&1 \
  && node quickstart.mjs "$CP_URL" "$WS_URL" ) | tee "$OUT/ts-quickstart.log"

echo "== hashes"
( cd "$OUT/dist" && sha256sum * ) | tee "$OUT/SHA256SUMS"
echo "SDK qualification passed"
