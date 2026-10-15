# Phase 01 — Truthful Latency Telemetry

**Status:** NOT STARTED

**Goal:** Measure one turn from actual speech end to audible playback with consistent clocks, turn correlation, and matching worker/SDK/demo schemas.

**Depends on:** Phase 00.

**Audit coverage:** L05, L09, I11 latency portion.

## Human gate before implementation

Resolve H03: agree that the primary user metric is acoustic end-of-speech to first audible sample. If the contractual thresholds remain open, implement measurements but label SLO evaluation provisional.

## Files and interfaces

- Modify: `core/latency/waterfall.py`, `core/latency/playback.py`, `core/latency/collector.py`.
- Modify: `worker_raw/orchestration/latency_hooks.py`, `worker_raw/orchestration/pipeline.py`, `worker_raw/ws_session.py`.
- Modify: `sdk/shared/event_schema.json`, Python/TS clients, and `examples/web-client/index.html`.
- Create: `tests/latency/test_waterfall_contract.py`, `tests/latency/test_client_ack.py`.
- Produce: versioned `metric.latency` payload with `session_id`, `turn_id`, `clock_domain`, raw stage timestamps/durations, `measurement_quality`, queue/drop data, and schema version.

## Tasks

- [ ] Write contract tests showing current worker payload and demo/SDK consumers disagree.
- [ ] Replace mutable session-wide “current waterfall” lookup with turn-ID correlation and reject stale/unknown playback acknowledgments.
- [ ] Remove fabricated VAD timestamps, 220 ms substitution, 800 ms cap, and server-enqueue-as-playback claims; missing data remains null with a reason.
- [ ] Use server monotonic time for server stages. Client sends its local playback event with turn ID; server records receipt separately and never subtracts unrelated clock domains.
- [ ] In the browser, emit `playback_started` when the first AudioBufferSource actually starts; include scheduled time and turn ID. Record underrun/prebuffer state.
- [ ] Generate Python and TS event types or validate both from the shared schema; update demo field names.
- [ ] Add histogram buckets or an explicit percentile aggregator so p50/p95 are based on a population, not one turn compared to a p50 target.
- [ ] Add tests for late ack, duplicate ack, clock reset, disconnect, missing VAD, overlapping turns, and barge-in.
- [ ] Update SDK protocol docs from the canonical schema.

## Verification

```powershell
python -m pytest tests/latency/test_waterfall_contract.py tests/latency/test_client_ack.py -q
python -m pytest tests/latency tests/e2e/scenarios/test_barge_in_e2e.py -q
```

Expected: no synthetic timestamps; each ack updates only its turn; SDK/demo accept the emitted schema; offline report distinguishes acoustic/VAD/server/client intervals.

## Human verification

Hamzi opens the demo, completes three offline fixture turns, and returns a screenshot or sanitized metric table. This is free/local. The executor supplies the exact launch command when implementing.

## Exit criteria

- One canonical latency event works across server, clients, and demo.
- Product and component metrics are explicitly distinguished.
- Phase 00 results can be regenerated under the new schema and become the comparison baseline for Phases 02–04.
