#!/usr/bin/env bash
# Regenerate (or, with --check, verify) requirements/runtime.txt: the
# hash-pinned export of uv.lock that every service image installs from.
#
#   bash scripts/release/export_requirements.sh          # rewrite the file
#   bash scripts/release/export_requirements.sh --check  # exit 1 if stale
set -euo pipefail

cd "$(dirname "$0")/../.."
UV=(uv)
command -v uv >/dev/null 2>&1 || UV=(python -m uv)

TARGET=requirements/runtime.txt
ARGS=(export --frozen --no-dev --no-emit-project --no-emit-workspace
      --extra knowledge-s3 --format requirements-txt)

if [[ "${1:-}" == "--check" ]]; then
  fresh="$(mktemp)"
  trap 'rm -f "$fresh"' EXIT
  "${UV[@]}" "${ARGS[@]}" -o "$fresh" >/dev/null 2>&1
  # The header line records the output path; compare everything after it.
  if diff <(tail -n +3 "$fresh") <(tail -n +3 "$TARGET") >/dev/null; then
    echo "$TARGET matches uv.lock"
  else
    echo "$TARGET is stale: run bash scripts/release/export_requirements.sh" >&2
    exit 1
  fi
else
  "${UV[@]}" "${ARGS[@]}" -o "$TARGET" >/dev/null
  echo "wrote $TARGET"
fi
