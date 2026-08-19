# Phase 02: Stream Buffering and Backpressure Policy

## 1. Executive Summary & Core Logic

Standardize bounded async queues between transport, VAD, STT, LLM chunker, and TTS egress with explicit overflow semantics. Fixes v3 unbounded transcript queue (AUDIT_01 §5) and MULTI inconsistent drop-newest on VAD queue (AUDIT_03 §5). Implements blueprint File 02 §1.1 queue table as enforceable policy objects, not ad hoc `asyncio.Queue` calls scattered in transport code.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `asyncio.Queue` with typed wrappers | Matches all four legacy async patterns; minimal new abstraction |
| `core/buffers/policy.py` config objects | Single source of truth for maxsize + overflow enum |
| Structured overflow counters | Feeds Phase 07 metrics (`buffer_drop_total`) |
| `asyncio.Event` for interrupt (v3 pattern) | Proven barge-in signal — `legacy_codebases/AI_voice_agent_v3 - gemini/backend/app/transport/audio_sender.py` |

**Reference docs:** blueprint File 02 §1.1; asyncio queue docs; avoid unbounded queues anti-pattern (File 09 §5).

## 3. What / How / Why

- **What:**
  - `BufferPolicy`: `name`, `maxsize`, `overflow: Literal["drop_oldest", "drop_newest", "block"]`
  - `TypedAsyncQueue[T]` wrapping put/get with policy enforcement and metrics hook
  - Standard queue names + defaults:

    | Queue | maxsize | overflow |
    |---|---:|---|
    | inbound_mic | 100 | drop_oldest |
    | vad_internal | 100 | drop_oldest |
    | transcript_partial | 200 | drop_oldest (partials only) |
    | transcript_final | unbounded* | block (*finals never dropped — policy guard) |
    | outbound_tts | 200 | block |
    | sentence_bridge | 50 | drop_oldest |

  - `CancellationToken` shared across producer/queue/transport (File 02 §3.3)
- **How:** Finals bypass drop logic via separate queue or priority flag; partial transcript eviction drops oldest partial only. Outbound TTS uses blocking put — TTS producer awaits rather than dropping speech frames. Overflow increments per-queue counter and emits DEBUG structured log with session_id.
- **Why this approach:** Dropping outbound audio causes audible glitches (AUDIT_01 §5 backpressure rationale). Drop-oldest inbound keeps VAD on freshest audio. Alternative: single ring buffer — rejected because transcript and audio have different loss tolerance.

## Deliverables

- `core/buffers/__init__.py`
- `core/buffers/policy.py` — `BufferPolicy`, overflow enum, default policy table
- `core/buffers/typed_queue.py` — `TypedAsyncQueue[T]` with metrics hooks
- `core/buffers/final_transcript_queue.py` — finals-never-dropped guard + watermark counter
- `core/buffers/cancellation.py` — `CancellationToken` protocol + `AsyncioCancellationToken`
- `core/buffers/defaults.yaml` — named queue configs (inbound_mic, outbound_tts, etc.)

## 4. Compute & Resource Profile (if applicable)

Worst-case buffered audio: inbound 100 frames × 1024 B ≈ 100 KB; outbound 200 × 1024 B ≈ 200 KB per session. 100 concurrent sessions ≈ 30 MB queue memory — acceptable on 8 GB worker. Blocking outbound backpressure adds latency to TTS producer, not client playback — expected under load.

## 5. Compliance Notes (if applicable)

Transcript queues may hold PHI text. Queue dump/debug endpoints forbidden in production. Overflow logs record counts only, not transcript content.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Final transcript "unbounded" safety:** high watermark alert at **500** pending finals (bug indicator) without dropping.
2. **Cross-process queues:** Redis streams deferred to Phase 17 orchestration; in-process only in this phase.
3. **`sentence_bridge` maxsize:** **50** with metric alert; tunable per tenant later (Phase 14).

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_02_stream_buffering.py`
- **Asserts:** inbound drop-oldest retains newest N items; outbound blocks when full; finals never dropped under synthetic flood; overflow counters increment; cancel token checked in send loop mock.
- **Pass threshold:** 100% policy tests; no final transcript loss in 10,000 partial flood test.
- **Latency target:** drop_oldest operation < 1 ms p99 per frame at maxsize.
