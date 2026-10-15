# Cleanup Execution Tracker

| Phase | Status | Evidence | Verification | Notes |
|---:|---|---|---|---|
| C00 | COMPLETE | Clean `wavia-fixv1` at `2c5ad00`; inventory and Phase 00 handoff captured | `git diff --check` passed; documents reviewed | Production Phase 01 remains untouched |
| C01 | COMPLETE | `.pytest_cache`, `.ruff_cache`, and stale `.venv` moved to ignored quarantine | Canonical imports passed; `tests/latency`: 15 passed in 0.40s | 6,633 files; 228,711,901 bytes quarantined; no tracked application change |
| C02 | READY | Reference scan found no active imports of old harness paths | Pre-move verification pending | Proven duplicate tracked harnesses only |
| C03 | NOT STARTED | - | - | Compatibility/package boundary audit |
| C04 | NOT STARTED | - | - | Minimal realignment only when justified |
| C05 | NOT STARTED | - | - | Preserve useful roadmap/reference material |
| C06 | NOT STARTED | - | - | Offline regression and final report |

## Next exact action

Start C02 by running the pre-move reference scan and focused tests, recording Git object IDs for the four tracked old-harness files, and moving only those files into `hamza_local/clean_codebase/tracked/latency-harnesses/`. Stop before C03.

## Known pre-existing regression baseline

Before cleanup, the focused voice suite had 64 passing tests and 3 failures:

1. Speech-capture onset did not activate after the expected loud-frame count.
2. Control-plane quick mint returned HTTP 401 where the test expected 200.
3. WebSocket turn setup inherited the same quick-mint 401.

These failures are not cleanup regressions. Any additional failure blocks the cleanup phase.
