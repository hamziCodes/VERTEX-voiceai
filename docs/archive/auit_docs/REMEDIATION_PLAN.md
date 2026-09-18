# UCVE Audit Remediation Plan (R0–R7)

**Created:** 2026-08-27  
**Scope:** Production-path defects verified against current code (Phases 00–25 surface). Phases 26–35 deferred.  
**Protocol:** Implement one level → tests → `pytest -q` green → update this table + `EXECUTION_TRACKER.md` → user confirms → next level.  
**Constraints:** No commits unless asked; never touch API-keys / `.env`; streaming providers mock-default (`RUN_LIVE_PROVIDERS=1` opt-in); resampler stays numpy.

---

## Status Overview

| Level | Title | Findings | Status | Sign-off |
|---|---|---|---|---|
| R0 | Regression Harness Foundation | Phase 33 prerequisite | `COMPLETED` | 2026-08-27 |
| R1 | Live Voice Path Restoration | C1, M2, H1 | `COMPLETED` | 2026-08-29 |
| R2 | Turn Lifecycle, Barge-In & VAD Realism | C5, C4, C3, M4, M6 | `COMPLETED` | 2026-08-29 |
| R3 | True Streaming Pipeline | C2, O1, O3, H5, H6, M5, M1 | `COMPLETED` | 2026-08-29 |
| R4 | Honest Measurement & Bounded Resources | H8, H7, M3, O4, O2 | `COMPLETED` | 2026-08-29 |
| R5 | Transport, Failover & Config Truth | H2, H3, H4, H10, M7–M10 | `COMPLETED` | 2026-08-29 |
| R6 | Control-Plane Security Hardening | H9 | `COMPLETED` | 2026-08-29 |
| R7 | Prior-Audit Carryovers (18–25) | Phase partials | `COMPLETED` | 2026-08-29 |

Status values: `PENDING` / `IN_PROGRESS` / `READY_FOR_MANUAL_TEST` / `COMPLETED`

---

## R0 — Regression Harness Foundation

**Why:** Phase 33 harness is a stub (`run()` always returns `True`). Without a real scenario registry + red gate for C1, later remediations cannot prove regressions stay fixed.

### Deliverables

| Path | Change |
|---|---|
| `tests/e2e/harness.py` | `ScenarioResult(passed, failures, metrics)`; scenario registry + dispatch; `run()` returns False on failure |
| `tests/e2e/scenarios/sovereign_conversation.py` | In-process mock stack: admit → text turn → mock LLM → TTS → barge-in mid-TTS → cancel asserts → second turn → teardown → post-call enqueue |
| `tests/e2e/test_harness_gate.py` | Harness False on injected failure; sovereign scenario passes under mocks |
| `tests/hardening/test_h2_http_ws.py` | Binary-PCM ingress regression as `xfail(strict=True)` (red gate for C1) |

### Gate

- Harness returns `False` when a scenario injects failure.
- Existing suite stays green (xfail expected-fail only for C1 PCM ingress).
- `sovereign_conversation` exercises mock LLM + TTS + barge-in cancel + post-call enqueue.

### R0 completion notes (2026-08-27)

- `ScenarioResult` + registry dispatch live in `tests/e2e/harness.py`.
- `sovereign_conversation` registered and covered by `tests/e2e/test_harness_gate.py`.
- C1 red gate: `test_binary_pcm_frame_ingress_no_typeerror` (`xfail(strict=True)`).
- Suite: `256 passed, 1 skipped, 1 xfailed`. Integrity script OK.
- Minor: fixed JWT test secret typo in `test_h1_auth_crypto.py`; scoped `[tool.pytest.ini_options]` to exclude `legacy_codebases`.

### Out of scope (R1+)

Fixing C1 (`AudioFrame` kwargs), frame-size DoS, UUID fail-closed — R0 only **detects** C1 via xfail.

---

## R1 — Live Voice Path Restoration (C1, M2, H1)

**Verified defect (C1):** `worker_raw/main.py` constructs `AudioFrame(pcm_data=..., channels=1)` but canonical contract is `pcm16` / `channel_count` (`core/types/audio.py`).

### Deliverables

| ID | Change |
|---|---|
| C1 | `AudioFrame(pcm16=pcm_data, sample_rate=16000, channel_count=1)` |
| M2 | uvicorn `ws_max_size=256_KB` + `MAX_AUDIO_FRAME_BYTES` → error event + close |
| H1 | `parse_uuid(value, field)` raising typed `UCVEErrorCode`; replace 3 `UUID(x) if len(x)==36 else uuid4()` sites in `pipeline.py` |
| Tests | Flip R0 xfail → strict pass; malformed-tenant-ID test |

### Gate

- Binary frame → no `TypeError`, VADEvent returned.
- 10 MB frame → connection rejected.
- 35-char tenant_id → typed error, zero tenant-scoped writes.

---

## R2 — Turn Lifecycle, Barge-In & VAD Realism (C5, C4, C3, M4, M6)

| ID | Change |
|---|---|
| C5 | Inbound `TypedAsyncQueue` + single turn-worker; `active_turns` as set + `add_done_callback`; disconnect cancel + gather → **`finalize_session()`** (extract from `run()` finally; currently never on WS path) |
| C4 | VAD `speech_start` → FSM `VAD_SPEECH_START` → `BargeInController` → `ThreePointCancel.execute_cancel_and_flush()` (LLM+TTS registered; no await in receive loop); `InterruptBuffer.next_turn_input()` for next turn |
| C3 | `await asyncio.to_thread(vad.process_frame, frame)`; numpy-vectorized energy fallback |
| M4 | min-speech/min-silence hangover; logged backend fallback; Silero state-tensor windows when available |
| M6 | Event-driven FSM triggers; exception-safe FSM teardown in `run_turn` |

### Gate

- 3 rapid `text_turn`s serial; one TTS task; no `InvalidStateTransitionError`.
- VAD speech mid-TTS → `BARGE_IN_INTERRUPTED`, TTS cancel <50 ms, LLM cancelled, buffer carries utterance.
- Loop stall <2 ms/frame; glitchy VAD → no event chatter; disconnect → teardown exactly once.

---

## R3 — True Streaming Pipeline (C2, O1, O3, H5, H6, M5, M1)

| ID | Change |
|---|---|
| H5 | One long-lived `httpx.AsyncClient` per provider + `aclose()` |
| C2a | Groq `"stream": True` + SSE deltas → `LLMStreamChunk` |
| C2b/O1 | Sentence pipelining: LLM → `SentenceChunker` → bounded TTS queue; TTS consumer starts on first sentence |
| C2d/O3 | Per-sentence TTS chunked stream; Gladia bytearray cap + partial finals; Gladia streaming-WS behind `RUN_LIVE_PROVIDERS` |
| H6 | Per-chunk cancellation checks; `aclose()` on generator teardown |
| M5/M1 | Egress `TypedAsyncQueue` (DROP_OLDEST) + sender; ingress queue decouples receive from VAD |

### Gate

- Mock 3-sentence stream → first TTS before LLM exhausts; TTFB <400 ms.
- Mid-stream cancel at chunk 2 → `aclose` observed, no leaked sockets.
- Slow egress → drops per policy, no stall.

---

## R4 — Honest Measurement & Bounded Resources (H8, H7, M3, O4, O2)

| ID | Change |
|---|---|
| H8 | Stamp `tts_ttfb_ms` on first yielded TTS chunk; `stt_final_ms` from real STT final; `playback_start_ms` at first successful egress (delete `+50`); fire `TTS_FIRST_BYTE` / `TTS_DRAINED` correctly |
| H7 | `collected_waterfalls` → `deque(maxlen=...)`; `clear_session()` in `finalize_session()`; `LTRIM` after RPUSH |
| M3 | Real per-turn monotonic timestamps → `DiarizedTurn` (delete `start_ms=0, end_ms=1000`) |
| O4 | Populate sequence/timestamp on binary frames |
| O2 | `_tone_pcm` → `b"\x00\x00" * n` |

### Gate

- Injected delays (STT 80 / TTFT 200 / TTS TTFB 120) → recorded ±20 ms; SLO breach alert fires.
- Soak (scaled 200 sessions) RSS growth <50 MB; Redis keys absent after teardown.

---

## R5 — Transport, Failover & Config Truth (H2–H4, H10, M7–M10)

| ID | Change |
|---|---|
| H2 | `last_pong_monotonic` deadline → teardown at 2× ping interval |
| H3 | `close()` closes socket; `is_connected` lifecycle; typed `ConnectionError` in sender |
| H4 | Route STT/LLM/TTS through `FailoverRouter`; streaming-generator failover + `subsequent_chunk_timeout`; process-global breaker; Null fallbacks |
| H10 | Numpy-vectorized resampler + one-sample carry + anti-alias; delete no-op `itemsize` |
| M7 | Model/voice from `PipelineSessionConfig` (not hardcoded `llama-3.1-8b-instant`) |
| M8 | Public accessor replacing `_compliance_profiles` private access |
| M9 | Typed `UCVEErrorCode` (BAA) + `ClientErrorMapper` vs raw `PermissionError` |
| M10 | Bare `CancelledError()` |

### Gate

- Dropped pongs → socket closed, teardown once.
- 5× primary failures → circuit opens, secondary <10 ms.
- Resampler sweep — no aliasing energy, boundary continuity, ≥100× realtime.

---

## R6 — Control-Plane Security Hardening (H9)

| Change | Detail |
|---|---|
| Auth on mint | `/mint` + `/v1/session/mint` require API-key unless `UCVE_DEMO_MODE=1` (off by default) |
| CORS | Explicit `UCVE_ALLOWED_ORIGINS`; never wildcard+credentials |
| Role | From verified JWT / API-key record only; ignore spoofable `X-Actor-Role` |
| Tenant header | `X-Tenant-Id` only with valid credentials |
| Docs/env | `.env.example` + `examples/host-backend` updated for demo mode |

### Gate

- Unauth `/mint` → 401 (demo off).
- Spoofed `X-Actor-Role: platform_admin` → 403.
- Non-allowlisted credentialed preflight rejected.
- Demo flow works with `UCVE_DEMO_MODE=1`.

---

## R7 — Prior-Audit Carryovers (Phases 18–25)

**Verify current state first**, then close gaps:

| Phase | Work |
|---|---|
| 18 | Telnyx signature fail-closed; DID→tenant binding (no silent default-tenant) |
| 19 | Real `health_check()` (config/credential validation); audio I/O stubs typed+documented or implemented |
| 21 | Webhook 3× exponential backoff; durable Redis/DB review queue |
| 22 | MCP transport basics beyond `tool:` prefix |
| 25 | `AlertRouter` log + webhook channels wired |

### Gate

- Signature fail-closed test; DID binding test; backoff (mock clock); durable queue; health-check false-on-bad-config; alert dispatch test.

---

## Execution Checklist (per level)

1. Implement level changes (small coherent edits per finding).
2. Add/extend tests under `tests/hardening/`, `tests/e2e/`, and phase tests as needed.
3. Run full suite from repo root — all green required.
4. Update this status table + `EXECUTION_TRACKER.md` remediation notes.
5. Report level summary → **user confirms** → proceed.

---

## Assumptions (locked)

- Phases 26–35 excluded from this program.
- Live provider verification is manual/opt-in via `RUN_LIVE_PROVIDERS=1`.
- No new `soxr` dependency.
- No git commits unless explicitly requested.
- API-keys file and `.env` never read or modified.

---

## Completion Summary (2026-08-29)

All remediation levels R0–R7 implemented and verified:

```
pytest tests/ voice_engine_plan/tests/ -q  →  267 passed, 1 skipped
python voice_engine_plan/scripts/verify_plan_integrity.py  →  OK
```

Key new modules: `worker_raw/ws_session.py`, `core/errors/parse_uuid.py`, `tests/hardening/test_remediation_r1_r7.py`.
