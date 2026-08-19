# Phase 04: Barge-In Arbitration and Recovery Rules

## 1. Executive Summary & Core Logic

Codify the full interruption protocol: verify-then-commit barge-in, atomic cancel/flush across LLM/TTS/sender, client control event, and **retention of the interrupting utterance** as the next turn input. Merges v3 cancel/flush lock (`legacy_codebases/AI_voice_agent_v3 - gemini/backend/app/transport/websocket.py` `_barge_in()`) with MULTI 700 ms / 300 ms verification window (`legacy_codebases/Multilingual_AI_Voice_Agent_gittracked/backend/app/orchestration/session.py`). Explicitly fixes v3 debt D4: finals during `_speaking_until` must not be discarded (AUDIT_01 §3).

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| FSM states `BARGE_IN_VERIFY` / `BARGE_IN_INTERRUPTED` (Phase 03) | Verification as first-class state, not inline sleep |
| Shared `CancellationToken` + `asyncio.Task.cancel()` | v3 interrupt event + task cancellation pattern |
| `AudioSender.flush()` draining outbound queue | AUDIT_01 §3 step 4 |
| Text backup trigger: final word_count > 3 during agent speech | MULTI path C — AUDIT_03 §3 |
| Wire event `control.barge_in` (JSON) | Unified vocabulary File 08 §3; legacy `{type:control,action:barge_in}` |

**Reference docs:** blueprint File 02 §3; habiba LiveKit params documented as **media hints only** for optional adapter — `false_interruption_timeout=0.7`, `resume_false_interruption=False`.

## 3. What / How / Why

- **What:**
  - `BargeInController` coordinating: pause TTS playout → verify window (700 ms max, 300 ms sustained speech) → commit or resume
  - `BargeInConfig`: `verify_window_ms=700`, `min_sustained_speech_ms=300`, `text_backup_word_threshold=3`, `reentrancy_guard=True`
  - `InterruptBuffer`: holds STT partials/finals through transition; first post-commit final becomes next turn input
  - Three-point cancel check: TTS producer, sender loop, client flush signal (File 02 §3.3)
- **How:**
  1. VAD speech-start during `AGENT_SPEAKING` → `BARGE_IN_VERIFY`, pause (do not cancel yet) TTS playout
  2. If sustained speech ≥ 300 ms within 700 ms window → commit: set interrupt flag, cancel LLM task, `tts.cancel_active()`, `sender.flush()`, emit `control.barge_in`, `vad.reset()`, `_speaking_until=0`, → `LISTENING`
  3. Else false alarm → resume TTS, → `AGENT_SPEAKING`
  4. Parallel path: STT final with word_count > 3 during `PROCESSING_INFERENCE` or `AGENT_SPEAKING` triggers immediate commit (MULTI backup)
  5. Reentrancy: `_barge_in_active` guard ignores duplicate triggers until `LISTENING` restored
- **Why this approach:** v3 immediate barge causes false positives from noise; MULTI verification reduces that at cost of 700 ms worst-case delay on real interrupts — acceptable tradeoff for production. Habiba LiveKit-only interruption is not sufficient for sovereign path (File 02 §3.2). Alternative: shorter 400 ms window — tunable via config; default stays 700 ms until measured on target hardware.

## Deliverables

- `core/fsm/barge_in_config.py` — `BargeInConfig` defaults (700/300/3)
- `core/fsm/interrupt_buffer.py` — `InterruptBuffer` for post-barge utterance retention
- `core/fsm/barge_in.py` — `BargeInController`, verify/commit logic, reentrancy guard
- `core/fsm/cancel_contract.py` — three-point cancel check interface (producer/queue/transport)
- `core/types/events.py` — add `ControlEventBargeIn` wire shape (`control.barge_in`)

## 4. Compute & Resource Profile (if applicable)

Verification window adds 0–700 ms latency before interrupt takes effect on false-positive path only; real interrupts detected at 300 ms sustain. Cancel + flush must complete < 50 ms p99 after commit (no audio frame post-cancel may egress). LLM cancel depends on provider streaming stop — budget 100 ms additional for in-flight token drain.

## 5. Compliance Notes (if applicable)

Interrupting utterance text in `InterruptBuffer` is PHI-capable — buffer cleared on session end; never logged at INFO. `control.barge_in` events contain no transcript.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Pause vs cancel during verify:** pause TTS playout during verify; if provider lacks pause/resume, mute outbound queue during verify instead.
2. **700 ms vs habiba 0.7 s LiveKit:** aligned by design (700 ms verify window); tenant-tunable via `BargeInConfig` later.
3. **Managed transport plane:** when LiveKit adapter active, FSM still owns commit decision; SFU hints do not bypass `BargeInController` (Phase 18 telephony integration confirms).

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_04_barge_in.py`
- **Asserts:** false alarm < 300 ms resumes without cancel; sustained speech commits cancel; no outbound frame after commit (mock sender); interrupt utterance available as next turn input; reentrancy guard; text backup > 3 words triggers commit; `control.barge_in` emitted once per commit.
- **Pass threshold:** 100% scenario tests; zero post-cancel frames in 1000-iteration fuzz.
- **Latency target:** commit path (cancel+flush) < 50 ms p99; verify window timing ± 20 ms.
