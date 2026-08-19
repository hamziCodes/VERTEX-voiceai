# Phase 17: Real-Time Orchestration Pipeline Integration

## 1. Executive Summary & Core Logic

Wire Phases 01–16, 05–07, 13–14 into a single in-process call pipeline: transport → **VAD** → STT → language router → LLM → normalizer/chunker → TTS → egress, governed by Phase 03 FSM and Phase 04 barge-in. This is the first **end-to-end talking session** milestone. Harvests integration shape from v3 `SessionOrchestrator` (`legacy_codebases/AI_voice_agent_v3 - gemini/backend/app/transport/websocket.py`) and MULTI `orchestration/session.py` — but **only through Phase 05 interfaces**, never concrete Gladia/Groq imports. LiveKit optional stub only. Depends on Phase 13 WS JWT auth and Phase 07 correlation IDs throughout.

**VAD adapter:** Phase 05 defined `BaseVADProvider`; this phase wires the real Silero+energy hybrid adapter (MULTI `vad_service.py` pool pattern) into the pipeline — not deferred.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `PipelineOrchestrator` in `worker-raw/` | Sovereign plane first (blueprint File 09 Phase 1) |
| `NativeWebSocketTransport` | v3/MULTI `/ws/audio` pattern |
| `SileroVADAdapter` via Phase 05 `BaseVADProvider` | MULTI pool + energy fallback — required for demo quality |
| Phase 06 `FailoverRouter` for all provider calls | No inline try/except |
| `asyncio.TaskGroup` for STT/LLM/TTS tasks | Clean cancel on barge-in (Phase 04) |
| Redis hot session state | Horizontal scaling prep (File 01 §3.3) |
| Phase 14 heartbeat + usage flush on disconnect | Admission + billing truth |

**Reference docs:** blueprint File 09 §2 Phase 1 exit criteria; File 01 §3.4 transport gateway.

## 3. What / How / Why

- **What:**
  - `PipelineOrchestrator`: owns session lifecycle; wires queues (Phase 02), FSM (Phase 03), barge-in (Phase 04)
  - **`SileroVADAdapter`** (Phase 05 interface): pooled Silero + energy fallback; feeds speech frames to STT
  - `NativeWebSocketTransport`: binary PCM in, PCM + JSON control out; JWT validate (Phase 13); ping 20 s (v3 AUDIT_01 §4)
  - **`RedisSessionStore`:** hot turn history + ephemeral session flags — TTL aligned with session max duration; enables multi-worker routing later even if v1 runs single-worker
  - **Basic reconnect:** client disconnect → session ends cleanly; client reconnect with **new** JWT mint → new session. Emit `control.pong` handling (File 7 §3.2). **Full resilience** (exponential backoff, cross-worker session resumption, Phase 03 FSM restore) — `[LATER]`; must not expand into Phase 03 FSM rebuild
  - Stage boundaries emit Phase 07 spans: `turn.stt`, `turn.llm`, `turn.tts`
  - Provider calls via Phase 06 registry only
  - TTS output: provider-native rate → **single resample at transport egress** (Phase 05 decision) to 16 kHz WS
  - Session end (disconnect handler): Phase 11 redaction hook → **`PostCallPipeline.enqueue(call_record)`** (Phase 20) assembles/persists post-call record → Phase 14 usage flush → Phase 12 audit (`call_record_created`)
  - `control.metric` events passthrough for SDK (v3/MULTI pattern)
- **How:** `worker-raw/main.py` accepts connections → `PipelineOrchestrator.run(session_config)`. Config loaded tenant-scoped from Phase 08. Agent provider chains from JSONB. Audio → VAD adapter → STT. On `stt_final`: router (Phase 15) → build messages → LLM stream → normalizer/chunker (Phase 16) → TTS stream. Barge-in cancels via Phase 04 controller. Redis writes on each turn final. Compliance: Phase 10 gate before cloud LLM if HIPAA without `hipaa_baa_acknowledged_at`.
- **Why this approach:** Until this phase, components are untested in combination. Habiba pipeline is LiveKit-coupled — not portable (AUDIT_04 §6). Owning orchestrator in `worker-raw` satisfies sovereignty mandate. Alternative: LiveKit Agents as orchestrator — rejected.

## Deliverables

- `worker-raw/main.py` — entrypoint
- `worker-raw/orchestration/pipeline.py` — `PipelineOrchestrator`
- `worker-raw/orchestration/session_config.py`
- `core/transport/__init__.py`
- `core/transport/base.py` — `BaseTransportGateway` protocol
- `core/transport/native_websocket.py`
- `core/transport/resample_egress.py` — single boundary resample
- `core/vad/silero_adapter.py` — Silero+energy hybrid implementing `BaseVADProvider`
- `core/session/redis_store.py` — `RedisSessionStore` hot state
- `worker-raw/handlers/session_lifecycle.py` — connect/disconnect/heartbeat/basic reconnect
- `docs/pipeline/RECONNECT_SCOPE.md` — documents basic vs `[LATER]` full resilience boundary
- `examples/web-client/` — minimal AudioWorklet client (port v3 `frontend/index.html` pattern)

## 4. Compute & Resource Profile (if applicable)

Single session CPU: ~0.3–0.5 core with Silero pool. Memory: ~150 MB + Silero pool (~50 MB). Redis: ~2 KB/session hot state. Target TTFB: design budget File 01 §4 (~450 ms) — measured in Phase 24 harness. 50 concurrent sessions: 4 vCPU / 8 GB worker minimum without GPU.

## 5. Compliance Notes (if applicable)

Pipeline must call Phase 11 redaction before any post-call or extraction-bound copy. Cloud LLM calls gated by Phase 10. Transcript persistence follows Phase 11 dual-column rules. Never log raw PCM/transcript at INFO+ (Phase 07).

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **VAD adapter:** wire Silero+energy hybrid via Phase 05 interface **in this phase** — required, not stub-only.
2. **Session state in Redis:** **yes** — hot turn history for future horizontal scaling; wired here.
3. **Reconnect/resume:** **basic reconnect only** (new session on reconnect); full resilience (backoff, cross-worker FSM restore) deferred `[LATER]` — scope documented in `RECONNECT_SCOPE.md`.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_17_pipeline_integration.py`
- **Asserts:** WS connect with valid JWT; VAD adapter produces speech frames; full turn STT→LLM→TTS with null/mock providers; barge-in mid-TTS; metric events emitted; usage flushed on disconnect; Redis turn history written; HIPAA gate blocks LLM without BAA ack; correlation IDs in all stage logs; reconnect creates new session (no silent FSM restore).
- **Pass threshold:** integration test completes 3-turn conversation; barge-in test passes Phase 04 criteria.
- **Latency target:** mock-provider turn < 500 ms; log waterfall present for each stage.
