# Cleanup Execution Tracker

| Phase | Status | Evidence | Verification | Notes |
|---:|---|---|---|---|
| C00 | COMPLETE | Clean `wavia-fixv1` at `2c5ad00`; inventory and Phase 00 handoff captured | `git diff --check` passed; documents reviewed | Production Phase 01 remains untouched |
| C01 | COMPLETE | `.pytest_cache`, `.ruff_cache`, and stale `.venv` moved to ignored quarantine | Canonical imports passed; `tests/latency`: 15 passed in 0.40s | 6,633 files; 228,711,901 bytes quarantined; no tracked application change |
| C02 | COMPLETE | Two unused test-layout files and generated caches quarantined; Git blob IDs recorded in manifest | `tests/latency`: 15 passed; 70 targeted tests collected; canonical latency Ruff passed | Runtime `core/latency/benchmarks` retained due runbook contract; 19 pre-existing Ruff findings recorded |
| C03 | COMPLETE | `STRUCTURE_DECISIONS.md` maps package, service, Docker, test, reference, and local-tool boundaries | Canonical imports passed; targeted layout/deployment set 17 passed/1 existing config-guard failure; UV exposed invalid lock | Compatibility paths must remain under current Phase 00 contract |
| C04 | COMPLETE - NO CHANGE | Naming analysis found underscore imports and hyphenated distributions/services are correctly separated | Existing layout tests and Docker consumers confirm contract | Broad rename would create breakage; public-path changes still require approval |
| C05 | NOT STARTED | - | - | Preserve useful roadmap/reference material |
| C06 | NOT STARTED | - | - | Offline regression and final report |

## Next exact action

Start C05 by reviewing the audit's stub/dead-code candidates one bounded group at a time. Begin with `core/latency/benchmarks`, `worker_raw/handlers/session_lifecycle.py`, and `worker_raw/telephony/inbound_handler.py`; classify public/docs/test consumers before moving or editing anything.

## Pre-existing lint debt found during C02

`py -3.12 -m ruff check tests/latency core/latency` reported 19 findings in the untouched `core/latency` package: long lines, import ordering, and unused imports. The canonical `tests/latency` suite passes Ruff. These findings were not caused by the two deleted test-layout files and are deferred to a focused cleanup/fix phase.

## Known pre-existing regression baseline

Before cleanup, the focused voice suite had 64 passing tests and 3 failures:

1. Speech-capture onset did not activate after the expected loud-frame count.
2. Control-plane quick mint returned HTTP 401 where the test expected 200.
3. WebSocket turn setup inherited the same quick-mint 401.

These failures are not cleanup regressions. Any additional failure blocks the cleanup phase.
