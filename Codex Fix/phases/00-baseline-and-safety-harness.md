# Phase 00 — Baseline and Safety Harness

**Status:** NOT STARTED

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

- [ ] Inventory current test commands, optional dependencies, markers, environment gates, and which tests write files or contact services.
- [ ] Define `LatencySample` fields for acoustic EOS, VAD end, STT final, RAG end, LLM first token, first speakable text, TTS first byte, server send, scheduled playback, acknowledged playback, drop counts, and turn ID.
- [ ] Add a deterministic fake streaming STT/LLM/TTS set with controllable first-chunk/inter-chunk delays and cancellation observations; test doubles identify themselves as `test` in telemetry.
- [ ] Build the corpus described in `VERIFICATION.md`; attach expected transcript/duration/sample-rate metadata.
- [ ] Add a network-denied test that fails if offline suite code attempts DNS/socket/HTTP/WebSocket access outside an explicitly local test server.
- [ ] Add a production-mode assertion that missing provider credentials returns a typed configuration/provider error and never mock text/tone.
- [ ] Create a baseline runner that produces JSON plus a concise table; do not overwrite prior evidence—use a new timestamped filename.
- [ ] Run the existing focused voice tests and record failures separately from new baseline results; do not “fix” them in this phase.
- [ ] Document exact hardware/browser/runtime information needed for browser measurements.

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

Record command, commit, result artifact, failures, hardware, and Hamzi decisions here when executed.
