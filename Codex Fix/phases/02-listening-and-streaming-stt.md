# Phase 02 — Listening Path and Streaming STT

**Status:** READY FOR FINAL QA

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

- [x] Repair the bundled Silero ONNX streaming contract with 64-sample rolling
  context and regression coverage.
- [x] Expose VAD transitions and mock/live transcript behavior truthfully to the
  demo console.
- [x] Verify speech onset against the local multilingual fixture set.
- [x] Add a regression proving STT is warmed before first speech and is not
  initialized again on that speech.
- [x] Start selected streaming STT during admitted-session initialization,
  before `ready`; bound startup timeout and clean up on every failure.
- [x] Reject readiness until warm-up resolves to live or explicit batch fallback,
  so pre-ready audio cannot be silently lost.
- [x] Select live STT from compiled provider configuration rather than hardcoded
  Gladia. Batch fallback is explicit and reported.
- [x] Separate local VAD onset/barge-in from provider endpointing. Feed continuous
  canonical frames while the session is active.
- [x] Test endpoint candidates around 400/550/650/960 ms using real and synthetic
  multilingual fixtures; record cutoff risk and added endpoint latency.
- [x] Make frame slicing mandatory at the transport boundary so millisecond
  thresholds do not depend on client packet size.
- [x] Define ingress queue policy: bounded blocking, explicit degradation metric,
  and no drop-oldest behavior under saturation.
- [x] Bound transcript queue and reconnect policy; preserve final ordering and
  prevent stale finals after reconnect.
- [x] Share the Silero ONNX graph and a two-thread VAD executor across sessions.
- [x] Cover short speech, pauses, low-volume/noise fixtures, Urdu-English cases,
  connect timeout, final ordering, stale reconnects, and queue saturation.

## Verification

```powershell
python -m pytest tests/listening/test_warm_stt_session.py tests/listening/test_endpoint_profiles.py tests/listening/test_ingress_backpressure.py -q
python -m pytest tests/listening tests/latency -q
```

Expected: STT ready before session ready; first audio retained; packet-size invariant endpoint behavior; no silent drops; each profile has comparative p50/p95 and cutoff/false-endpoint results.

## Human verification

Hamzi requested that audit and QA gates be deferred until all phases are
implemented. H04 therefore remains open; no production endpoint default was
changed. Live Gladia measurement still requires explicit cost approval.

## Exit criteria

- Provider handshake is absent from first-utterance latency.
- Endpoint choice is evidence-backed and language-aware.
- Ingress/transcript queues are bounded with observable failure.
- Phase 01 user metric improves without transcript loss/cutoff regression.
