# Codebase Cleanup Program

This program cleans repository clutter without beginning production remediation Phase 01. It runs independently from the voice-engine phases in `../phases/`.

## Safety rules

- Never read or move `.env`, `API KEYS*`, or other credential files.
- Never place live calls or invoke paid providers.
- Move recoverable clutter into the ignored `hamza_local/clean_codebase/` quarantine. Do not permanently delete it.
- Record every moved tracked file in `QUARANTINE_MANIFEST.md` with its original path and Git evidence.
- Keep compatibility paths, specifications, legacy comparison projects, and roadmap modules until a reference scan and focused tests prove they can move.
- Run focused verification after each phase. Stop on a new failure.
- Do not start Wavia production Phase 01 during this cleanup pass.

## Phase map

| Phase | Scope | Status |
|---:|---|---|
| C00 | Inventory, classification, rollback point, and Phase 00 handoff | COMPLETE |
| C01 | Quarantine generated local clutter | COMPLETE |
| C02 | Quarantine proven duplicate/dead tracked code | COMPLETE |
| C03 | Validate package boundaries and compatibility paths | COMPLETE |
| C04 | Align names and hierarchy where tests prove it is safe | COMPLETE - NO RENAME |
| C05 | Classify stubs, roadmap code, and historical/reference material | NOT STARTED |
| C06 | Full offline regression and final structure report | NOT STARTED |

## Current classification

### Keep in place

- `legacy_codebases/`: active latency comparison evidence requested by Hamzi.
- `docs/archive/`: historical evidence referenced by the audit.
- `voice_engine_plan/`: its phase tests are included by root pytest configuration.
- `control-plane/` and `worker-raw/`: compatibility paths required by Phase 00 layout tests and workspace naming.
- `agent-studio/`: referenced by agent-builder phase tests.
- `worker_managed/`: referenced by its Dockerfile.
- `.cursor/`, `.qoder/`, `.superpowers/`: local tool state; not proven disposable.

### Safe generated-clutter candidates

- `.pytest_cache/`
- `.ruff_cache/`
- stale `.venv/` after confirming system Python runs the required offline suite
- Python `__pycache__/` directories, except that scanning and moving them is deferred until tracked work is stable because they regenerate during verification

### Tracked duplicate cleanup

- `tests/latency-benchmarks/harness.py` and its generated cache were quarantined.
- `tests/latency_benchmarks/__init__.py` and its generated cache were quarantined.

The canonical Phase 00 suite is `tests/latency/`. Historical plan references remain unchanged as historical evidence. `core/latency/benchmarks/` remains in place because an operational runbook names its class; C05 must decide whether to repair that contract or retire it.

See `STRUCTURE_DECISIONS.md` for the full hierarchy map. C04 intentionally makes no broad naming change: underscore Python packages and hyphenated distribution/service names are valid, tested layers of the current structure.

## Resume point

Read `EXECUTION_TRACKER.md`, then perform its `Next exact action`. Do not skip phase gates.
