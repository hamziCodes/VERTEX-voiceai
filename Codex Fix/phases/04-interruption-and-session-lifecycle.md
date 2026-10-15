# Phase 04 — Interruption and Session Lifecycle

**Status:** NOT STARTED

**Goal:** Make interruption and teardown deterministic across provider generation, server queues, client playback, transcript retention, and resource cleanup.

**Depends on:** Phases 02–03.

**Audit coverage:** F07, F08, L10.

## Human gate before implementation

None for offline work. Human listening is recommended at exit. Do not choose a live-call behavior based only on synthetic audio.

## Files and interfaces

- Modify: `core/fsm/*`, `worker_raw/orchestration/pipeline.py`, `worker_raw/ws_session.py`.
- Modify: Python/TS SDKs and web client playback controller.
- Create: `core/playback/turn_commit.py` or equivalent focused played-text tracker.
- Create: `tests/e2e/scenarios/test_interruption_matrix.py`, `tests/e2e/test_session_cleanup.py`.
- Produce: `control.barge_in` with turn ID and monotonic sequence; `control.clear_audio` acknowledgment; played-text commit events.

## Tasks

- [ ] Reproduce interruption during STT, RAG, LLM, tool filler, TTS request, server egress, browser prebuffer, and active playback.
- [ ] Replace split event names with the canonical event defined in Phase 05-compatible schema; accept legacy alias only during an explicit deprecation window.
- [ ] Cancel the live LLM producer task, TTS producer/consumer, filler/tool work, provider HTTP streams, and egress sender safely; do not only set tokens.
- [ ] Clear provider/server/client buffers and require client clear acknowledgment. Prevent one dequeued server chunk from escaping after commit.
- [ ] Commit assistant context by actually played speech boundary; interrupted unsaid text never enters history.
- [ ] Retain pre-roll, partial and final interrupting user text exactly once as the next turn.
- [ ] Make verification resolve early when sustained speech/text evidence passes rather than always sleeping the full window; preserve false-alarm resume.
- [ ] Use a structured task group/resource owner so startup and teardown close live STT, HTTP clients, VAD tasks, verification tasks, queues, Redis state and admission leases.
- [ ] Ensure FSM returns to LISTENING only after client playout drain/ack, not merely synthesis completion.
- [ ] Test duplicate/concurrent barge, disconnect during each stage, client without ack, false noise, one-word/two-word policy, and rapid back-to-back turns.

## Verification

```powershell
python -m pytest tests/e2e/scenarios/test_interruption_matrix.py tests/e2e/test_session_cleanup.py -q
python -m pytest tests/listening/test_barge_verify_live.py tests/e2e/scenarios/test_barge_in_e2e.py -q
```

Expected: ≤100 ms offline stale audio; one retained user turn; no unplayed assistant context; zero orphan tasks/resources; false alarms resume without duplicated audio.

## Human verification

Hamzi performs a local browser interruption script and reports whether speech stops promptly and the agent answers the interruption. Exact free/local steps are supplied at execution.

## Exit criteria

- All interruption matrix cases pass.
- Session cleanup passes on normal close and failure at every startup/runtime stage.
- Playback completion and FSM state agree.
