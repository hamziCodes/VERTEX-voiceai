# Phase 02 — Listening Path and Streaming STT

**Status:** NOT STARTED

**Goal:** Remove first-utterance STT setup, reduce safe endpoint delay, and make ingress lossless-or-explicit under load across supported languages and packet sizes.

**Depends on:** Phases 00–01.

**Audit coverage:** L02, L07, L11, P03 listening side.

## Human gate before implementation

No choice is needed to implement candidates. Stop after A/B results and resolve H04 before choosing production endpoint defaults. Live STT cost measurement requires later explicit approval.

## Files and interfaces

- Modify: `worker_raw/ws_session.py`, `worker_raw/orchestration/pipeline.py`.
- Modify: `core/providers/adapters/gladia_live_stt.py`, provider STT interfaces/factory.
- Modify: `core/listening/config.py`, frame slicer, speech capture, VAD adapter/worker.
- Create: `core/providers/interfaces/live_stt.py` if one shared live-session contract is absent.
- Create: `tests/listening/test_warm_stt_session.py`, `test_endpoint_profiles.py`, `test_ingress_backpressure.py`.
- Proposed interface: `BaseLiveSTTSession.start()`, `send_audio(frame)`, `transcripts()`, `finish_turn()`, `aclose()` plus health/drop counters.

## Tasks

- [ ] Add a regression test proving the current first speech triggers STT session initialization.
- [ ] Start selected streaming STT during admitted-session initialization, before `ready`; bound startup timeout and clean up on every failure.
- [ ] Buffer pre-ready audio for a small bounded duration or reject readiness until STT is ready; never silently lose it.
- [ ] Select live STT from compiled provider configuration rather than hardcoded Gladia. Batch fallback is explicit and measured.
- [ ] Separate local VAD onset/barge-in from provider endpointing. Feed continuous canonical frames while the session is active.
- [ ] Test endpoint candidates around 400/550/650/960 ms using real/synthetic multilingual fixtures; record cutoff rate, false endpoint rate, and latency.
- [ ] Make frame slicing mandatory at the transport boundary so millisecond thresholds do not depend on client packet size.
- [ ] Define ingress queue policy: bounded capacity, age metric, explicit drop/degradation event, and no drop-oldest acceptance in normal load tests.
- [ ] Bound transcript queue and reconnect policy; preserve turn ordering and prevent duplicate finals after reconnect.
- [ ] Reuse/shared-load Silero model or a bounded executor based on measured concurrency; do not create uncontrolled per-session threads/models.
- [ ] Test short speech, long pause, low volume, noise, Urdu-English switching, disconnect during connect, provider final before/after local VAD, and queue saturation.

## Verification

```powershell
python -m pytest tests/listening/test_warm_stt_session.py tests/listening/test_endpoint_profiles.py tests/listening/test_ingress_backpressure.py -q
python -m pytest tests/listening tests/latency -q
```

Expected: STT ready before session ready; first audio retained; packet-size invariant endpoint behavior; no silent drops; each profile has comparative p50/p95 and cutoff/false-endpoint results.

## Human verification

Hamzi listens to A/B clips and selects the release profile (H04). If live Gladia measurement is needed, stop with the V5 request from `VERIFICATION.md`.

## Exit criteria

- Provider handshake is absent from first-utterance latency.
- Endpoint choice is evidence-backed and language-aware.
- Ingress/transcript queues are bounded with observable failure.
- Phase 01 user metric improves without transcript loss/cutoff regression.
