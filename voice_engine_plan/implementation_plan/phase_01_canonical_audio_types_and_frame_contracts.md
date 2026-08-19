# Phase 01: Canonical Audio Types and Frame Contracts

## 1. Executive Summary & Core Logic

Define immutable, transport-agnostic data types for audio frames, control events, and session identifiers that every adapter (WebSocket, LiveKit, SIP) must produce or consume. Canonical internal format is **16 kHz mono PCM16LE**, 512 samples (32 ms) per frame. Harvests v3 mic chunking and Silero window alignment (`legacy_codebases/AI_voice_agent_v3 - gemini/backend/app/transport/websocket.py`) and blueprint File 02 §1.2–1.3.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Pydantic v2 `BaseModel` + `@dataclass(frozen=True)` for hot paths | Validation at boundaries; frozen frames safe to pass across async tasks |
| `soxr` (preferred) or `resampy` | Resampling at transport edge only — not in hot loop (File 02 §1.2) |
| `enum.StrEnum` for event types | Stable wire + log serialization |
| `typing.Protocol` for frame producers | Transport adapters implement without inheriting heavy base |

**Reference docs:** blueprint File 02 §1.3; ITU-T G.711 for future telephony enum values (codec tag only, no impl here).

## 3. What / How / Why

- **What:**
  - `AudioFrame`: `pcm16: bytes`, `sample_rate: int` (16000 post-normalization), `timestamp_ms: float`, `sequence: int`, `channel_count: int = 1`
  - `AudioEncoding` enum: `PCM16`, `MULAW`, `OPUS` (wire-only; pipeline never sees non-PCM16)
  - `ControlEvent` union: `barge_in`, `flush`, `hangup`, `language_changed`, `metric`, `degraded_mode`, **`pong`** (`control.pong` — client response to server ping), **`playback_started`** (`control.playback_started` — client reports first audio output; Phase 24 playback metric)
  - `SessionId`, `CallId`, `TenantId` as branded `NewType` or UUID wrappers
  - `Resampler` wrapper class with `SUPPORTED_RATES = {8000, 16000, 22050, 24000, 44100, 48000}`
- **How:** Implement in `core/types/audio.py` and `core/types/events.py`. Validation: reject odd-length `pcm16`, reject `sample_rate != 16000` on frames entering VAD/STT path. Sequence monotonic per session; gap detection logs warning (no RTP in legacy repos — File 02 §1.3).
- **Why this approach:** v3 and MULTI passed raw bytes without sequence numbers, making latency debugging and reorder detection impossible (AUDIT_01 §5). Central types prevent each transport from inventing its own chunk size. Alternative: protobuf — rejected for Phase 1 complexity; JSON control + binary PCM matches legacy WS pattern.

## Deliverables

- `core/types/__init__.py`
- `core/types/audio.py` — `AudioFrame`, `AudioEncoding`, frame validators
- `core/types/events.py` — `ControlEvent` union + JSON serializers
- `core/types/ids.py` — `SessionId`, `CallId`, `TenantId` branded types
- `core/types/resampler.py` — `Resampler`, `SUPPORTED_RATES`
- `core/types/constants.py` — `CANONICAL_SAMPLE_RATE=16000`, `FRAME_SAMPLES=512`

## 4. Compute & Resource Profile (if applicable)

Per-frame memory: 1024 bytes PCM + ~200 bytes metadata. At 31.25 fps (512/16000), ~32 KB/s audio throughput per session — negligible. Resampler init: < 1 ms; per-chunk resample 8→16 kHz ~0.05 ms on modern CPU.

## 5. Compliance Notes (if applicable)

`AudioFrame` and derived buffers may contain PHI when healthcare tenants are active. Type metadata must include optional `contains_speech: bool` for redaction pipelines (Phase 10) but **must not** embed tenant PII in frame objects. Log serializers must never dump raw `pcm16` at INFO level.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Branded IDs vs plain UUID strings:** UUID v4 strings with runtime validation (Phase 08 schema).
2. **Nanosecond vs millisecond timestamps:** `float` monotonic ms (legacy pattern); OpenTelemetry span IDs added separately in Phase 07.
3. **Maximum frame size cap:** fixed **512 samples** (32 ms @ 16 kHz) for sovereign path; telephony adapter rebuffers in Phase 18.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_01_canonical_audio_types.py`
- **Asserts:** `AudioFrame` rejects invalid PCM length; sequence increments; resampler 8→16 kHz output length correct ±1 sample; control event JSON round-trip; frozen dataclass immutability.
- **Pass threshold:** 100% unit tests; resample spot-check RMSE < 1e-4 vs reference vector.
- **Latency target:** construct + validate 10,000 frames < 100 ms total.
