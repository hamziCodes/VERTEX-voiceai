# Codebase Cleanup Final Report

**Completed:** 2026-10-16  
**Branch:** `wavia-fixv1`

## Outcome

The cleanup program completed C00-C06 without beginning production remediation Phase 01 during the cleanup itself.

- Created a recoverable, Git-ignored quarantine at `hamza_local/clean_codebase/`.
- Quarantined the stale virtual environment and generated test/lint caches.
- Removed two tracked duplicate latency test layouts after reference, collection, and regression checks.
- Mapped package, service, Docker, SDK, roadmap, reference, and compatibility boundaries.
- Kept intentional underscore Python packages and hyphenated distribution/service names.
- Retained incomplete runtime capabilities when executable tests, upgrade plans, Dockerfiles, or future product contracts still consume them.
- Quarantined 79 generated `__pycache__` directories containing 424 files after final verification.
- Did not read, move, stage, or commit protected credential/key files.
- Did not place live calls, contact paid providers, deploy, or modify workflows.

## Tracked removals

Only these tracked files were removed from the working tree and preserved in the local quarantine plus Git history:

- `tests/latency-benchmarks/harness.py`
- `tests/latency_benchmarks/__init__.py`

The canonical latency suite is `tests/latency/`.

## Final offline verification

Command gates explicitly disabled live provider and live database tests.

- Full pytest: 420 passed, 1 skipped, 2 failed.
- Plan integrity: `OK: 36 phases, tests, and trackers verified.`
- Canonical package imports: passed.
- Phase 00 latency suite after tracked cleanup: 15 passed.
- Canonical latency Ruff check: passed.
- Targeted post-removal collection: 70 tests collected.

The two full-suite failures are in untouched VAD/listening behavior:

1. `tests/listening/test_speech_capture.py::test_process_frame_async_does_not_clear_on_onset`
2. `voice_engine_plan/tests/phase_tests/test_phase_17_pipeline_integration.py::test_vad_adapter_speech_detection`

They confirm the latency/listening defect that production Phases 01-03 are intended to measure and fix. They are not caused by cleanup file moves.

## Retained known defects

- Existing `uv.lock` is invalid for installed UV 0.13.1.
- Root `tool.uv.dev-dependencies` configuration is deprecated.
- Production-secret guard behavior is affected by import-time `.env` loading.
- `core/latency` has 19 pre-existing Ruff findings.
- Several worker jobs, provider routes, managed-worker paths, and telephony paths are incomplete and must not be advertised as production-ready.

These items belong to focused production phases because changing them affects dependency resolution, authentication, runtime behavior, or public capability contracts.

## Recovery

The exact quarantine mappings and Git blob IDs are in `QUARANTINE_MANIFEST.md`. The quarantine is local and ignored; tracked removed files are also recoverable from Git history.

## Next production action

Begin `../phases/01-truthful-latency-telemetry.md` using acoustic end-of-speech to first audible sample as the primary user-perceived metric. Contractual SLO thresholds remain provisional until production measurements exist.
