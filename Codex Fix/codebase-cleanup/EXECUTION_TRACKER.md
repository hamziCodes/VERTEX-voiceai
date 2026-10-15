# Cleanup Execution Tracker

| Phase | Status | Evidence | Verification | Notes |
|---:|---|---|---|---|
| C00 | COMPLETE | Clean `wavia-fixv1` at `2c5ad00`; inventory and Phase 00 handoff captured | `git diff --check` passed; documents reviewed | Production Phase 01 remains untouched |
| C01 | READY | - | - | Generated ignored artifacts only |
| C02 | NOT STARTED | - | - | Proven duplicate tracked harnesses only |
| C03 | NOT STARTED | - | - | Compatibility/package boundary audit |
| C04 | NOT STARTED | - | - | Minimal realignment only when justified |
| C05 | NOT STARTED | - | - | Preserve useful roadmap/reference material |
| C06 | NOT STARTED | - | - | Offline regression and final report |

## Next exact action

Start C01 by recording exact source/destination paths, confirming system Python works, then moving `.pytest_cache`, `.ruff_cache`, and the stale `.venv` into `hamza_local/clean_codebase/generated/`. Run the Phase 00 latency suite immediately afterward.

## Known pre-existing regression baseline

Before cleanup, the focused voice suite had 64 passing tests and 3 failures:

1. Speech-capture onset did not activate after the expected loud-frame count.
2. Control-plane quick mint returned HTTP 401 where the test expected 200.
3. WebSocket turn setup inherited the same quick-mint 401.

These failures are not cleanup regressions. Any additional failure blocks the cleanup phase.
