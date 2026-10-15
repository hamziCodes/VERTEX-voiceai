# Phase 00 — Baseline and Safety Harness

**Status:** IMPLEMENTED — AWAITING H01/H02

**Goal:** Establish a deterministic, free, network-denied baseline that can distinguish orchestration latency, correctness, audio quality, and fake-success behavior before any optimization.

**Audit coverage:** F05, latency L01–L11 baseline, existing-test limitations, all later regression gates.

## Human gate before implementation

Resolve H01 and H02 in `HUMAN_INPUT.md`. If Hamzi cannot provide representative audio immediately, create synthetic fixtures and mark language/real-speech acceptance `BLOCKED — HAMZI`; do not tune production thresholds from synthetic tones alone.

## Files

- Create: `tests/latency/fixtures/` manifest and non-sensitive audio fixtures or generators.
- Create: `tests/latency/test_pipeline_baseline.py`.
- Create: `tests/latency/test_no_live_network.py`.
- Create: `tests/latency/report.py` with `LatencySample` and percentile report types.
- Modify: `tests/conftest.py` only for explicit offline fixtures.
- Reference: `tests/e2e/`, `tests/latency_benchmarks/`, legacy Habiba `tests/test_latency.py`.

## Tasks

- [x] Inventory current test commands, optional dependencies, markers, environment gates, and which tests write files or contact services.
- [x] Define `LatencySample` fields for acoustic EOS, VAD end, STT final, RAG end, LLM first token, first speakable text, TTS first byte, server send, scheduled playback, acknowledged playback, drop counts, and turn ID.
- [x] Add a deterministic fake streaming STT/LLM/TTS set with controllable first-chunk/inter-chunk delays and cancellation observations; test doubles identify themselves as `test` in telemetry.
- [x] Build the corpus described in `VERIFICATION.md`; attach expected transcript/duration/sample-rate metadata.
- [x] Add a network-denied test that fails if offline suite code attempts DNS/socket/HTTP/WebSocket access outside an explicitly local test server.
- [x] Add a production-mode assertion that missing provider credentials returns a typed configuration/provider error and never mock text/tone.
- [x] Create a baseline runner that produces JSON plus a concise table; do not overwrite prior evidence—use a new timestamped filename.
- [x] Run the existing focused voice tests and record failures separately from new baseline results; do not “fix” them in this phase.
- [x] Document exact hardware/browser/runtime information needed for browser measurements.

## Verification

```powershell
python -m pytest tests/latency/test_no_live_network.py tests/latency/test_pipeline_baseline.py -q
python -m pytest tests/listening tests/providers tests/e2e -q
```

Expected evidence: offline network attempts = 0; explicit test providers reported; all corpus cases produce a record or typed expected failure; baseline artifact contains sample counts and p50/p95/p99; production mode produces no mock transcript/reply/tone.

## Human verification

If real speech fixtures are supplied, Hamzi confirms they are non-sensitive and representative. No live provider call is part of this phase.

## Exit criteria

- One command reproduces orchestration baseline without secrets/network.
- Timing schema and corpus are versioned.
- Existing failures are recorded rather than hidden.
- Later phases can compare results without changing measurement definitions.

## Evidence

- 2026-10-15: Phase started on `wavia-fixv1` from pushed checkpoint `1700041`.
- Runtime inventory: installed Python 3.12.10 and pytest 9.1.1 are available through `py -3.12`; repository `.venv` points to an obsolete Microsoft Store interpreter and is not usable.
- H01/H02 remain open. Synthetic fixtures are permitted for harness verification; real-language and listening acceptance remain `BLOCKED — HAMZI`.
- TDD red evidence: focused suite initially failed collection because `tests.latency.baseline` and `tests.latency.network_guard` did not exist; the generator contract then failed because `tests.latency.fixtures.generate` did not exist.
- Focused verification: `py -3.12 -m pytest tests/latency/test_no_live_network.py tests/latency/test_pipeline_baseline.py -q` → 11 passed in 0.30 seconds.
- Static verification: Ruff passed for all Phase 00 Python files; `compileall` passed; `git diff --check` passed.
- Baseline: 42 included, 0 excluded, p50 1.1 ms, p95 22.4 ms, p99 24.7 ms. This is scripted harness overhead, not provider or user-perceived production latency. Artifact: `evidence/phase-00/latency-baseline-20261015T151356930783Z.json`.
- Existing regression suite: 64 passed, 3 failed in 18.67 seconds. Failures are recorded in `evidence/phase-00/TEST_INVENTORY.md` and were not changed in this phase.
- Human setup and fixture fields are listed in `evidence/phase-00/HUMAN_BASELINE_INPUT.md`. Phase 01 must not begin until H01/H02 are answered or explicitly deferred by Hamzi.
