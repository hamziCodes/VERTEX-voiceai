# Phase 03: Core Session FSM and Turn Lifecycle

## 1. Executive Summary & Core Logic

Implement the authoritative call-state machine governing turn-taking from session admission through disconnect. States extend v3/MULTI three-state core (`LISTENING`/`THINKING`/`SPEAKING`) with explicit `CONNECTING`, `BARGE_IN_VERIFY`, `BARGE_IN_INTERRUPTED`, `TOOL_EXECUTING`, and strict transition guards. Fixes MULTI bug where invalid transitions were logged but still applied (AUDIT_03 §3). Lives in `core/fsm/`; transport and providers emit events, FSM owns legality.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Explicit enum `SessionState` + transition table | Testable; avoids LiveKit implicit states (habiba coupling) |
| `InvalidStateTransitionError` on illegal edges | File 02 §2.2 — guard side effects |
| Event-driven `TurnManager` | Decouples VAD/STT callbacks from state mutations |
| `CONNECTING` degraded admission | Fixes MULTI hard-reject when Silero unhealthy despite energy fallback |

**Reference docs:** blueprint File 02 §2; v3 `SessionOrchestrator` / `CallState` — `legacy_codebases/AI_voice_agent_v3 - gemini/backend/app/transport/websocket.py`; MULTI `CallStateManager` — `legacy_codebases/Multilingual_AI_Voice_Agent_gittracked/backend/app/orchestration/session.py`.

## 3. What / How / Why

- **What:**
  - States: `CONNECTING`, `LISTENING`, `USER_SPEAKING`, `PROCESSING_INFERENCE`, `TOOL_EXECUTING`, `AGENT_SPEAKING`, `BARGE_IN_VERIFY`, `BARGE_IN_INTERRUPTED`, `DISCONNECTED`
  - Events: `session_admitted`, `vad_speech_start`, `vad_speech_end`, `stt_final`, `llm_first_token`, `tool_call_start`, `tool_result`, `tts_first_byte`, `tts_drained`, `barge_verify_timeout`, `barge_confirmed`, `barge_false_alarm`, `hangup`, `disconnect`
  - `TurnContext`: session_id, current_language, turn_index, degraded_flags
  - Public API: `SessionFSM.trigger(event) -> SessionState`, `can_transition(event) -> bool`
- **How:** Transition table as dict[(state, event)] → (next_state, side_effect_hook). Side effects registered externally (start TTS only after confirmed `AGENT_SPEAKING`). `CONNECTING` completes with `degraded: {vad: "energy_fallback"}` when Silero health check fails but energy VAD available. Disconnect from any active state → `DISCONNECTED` (terminal).
- **Why this approach:** Habiba delegates FSM to LiveKit AgentSession (AUDIT_04 §6) — not portable. Owning FSM in `core/` keeps sovereign WS path first-class. Table-driven FSM vs hierarchical state machine: table wins for explicit auditability and phase-test coverage.

## Deliverables

- `core/fsm/__init__.py`
- `core/fsm/states.py` — `SessionState` enum
- `core/fsm/events.py` — `SessionEvent` enum
- `core/fsm/session_fsm.py` — `SessionFSM`, transition table, `trigger()` / `can_transition()`
- `core/fsm/turn_context.py` — `TurnContext` dataclass
- `core/fsm/errors.py` — `InvalidStateTransitionError`
- `core/fsm/transitions.yaml` — human-readable transition matrix (generated or hand-maintained)

## 4. Compute & Resource Profile (if applicable)

FSM operations are O(1) per event; negligible CPU. Memory per session: ~2 KB state + turn context. Target event processing < 0.1 ms p99 — must not block audio thread; run on same asyncio loop with strict no-blocking rule.

## 5. Compliance Notes (if applicable)

State transitions involving `stt_final` may carry PHI — transition logs record event type + session_id only, not transcript body. `DISCONNECTED` triggers hook for persistence/redaction pipeline (wired in Phase 11).

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **`USER_SPEAKING` vs staying in `LISTENING` on VAD start:** distinct `USER_SPEAKING` state for metrics (time-to-first-byte attribution).
2. **Reconnection mid-call:** **basic reconnect only** — disconnect ends session; client reconnects with new JWT mint → new session (Phase 17). Full cross-worker FSM restore deferred `[LATER]` (Phase 17 `RECONNECT_SCOPE.md`).
3. **Parallel tool calls:** **serial for v1** — one `TOOL_EXECUTING` at a time; parallel fan-out deferred to `[LATER]` (Phase 22 serial-tools decision).

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_03_session_fsm.py`
- **Asserts:** full happy-path transition chain; illegal transition raises `InvalidStateTransitionError` and state unchanged; disconnect from each non-terminal state; degraded CONNECTING path; turn_index increments on committed user turn.
- **Pass threshold:** 100% transition table coverage (every legal edge exercised; sampled illegal edges rejected).
- **Latency target:** 10,000 `trigger()` calls < 50 ms total.
