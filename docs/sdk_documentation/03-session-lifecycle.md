# Session Lifecycle

A Wavia session passes through a deterministic sequence of states, governed by the `SessionFSM` in `core/fsm/session_fsm.py`.

---

## State Machine Overview

The session FSM contains **9 states** and is driven by named events. State transitions are enforced via a compile-time transition table — any illegal transition raises `InvalidStateTransitionError`.

```
CONNECTING
    │ SESSION_ADMITTED
    ▼
LISTENING ◄────────────────────────── TTS_DRAINED ──────────┐
    │ VAD_SPEECH_START                                       │
    ▼                                                        │
USER_SPEAKING                                         AGENT_SPEAKING
    │ VAD_SPEECH_END / STT_FINAL                            ▲│
    ▼                                              TTS_FIRST_BYTE│VAD_SPEECH_START
PROCESSING_INFERENCE                                         ││
    │ TTS_FIRST_BYTE / TOOL_CALL_START                      ││ ──► BARGE_IN_VERIFY
    ▼                                                        │          │ BARGE_CONFIRMED
TOOL_EXECUTING                                               │          ▼
    │ TOOL_RESULT                                            │  BARGE_IN_INTERRUPTED
    └──────────────────────────────────────────────────────► ┘
```

---

## State Reference

| State | Description |
|---|---|
| `CONNECTING` | WebSocket handshake in progress; session not yet admitted |
| `LISTENING` | Idle — waiting for user speech onset via VAD |
| `USER_SPEAKING` | VAD detected speech start; buffering/streaming mic audio |
| `PROCESSING_INFERENCE` | STT final received; running RAG + LLM inference |
| `TOOL_EXECUTING` | LLM emitted a tool call; executing MCP/plugin tool |
| `AGENT_SPEAKING` | TTS first byte sent; streaming audio to client |
| `BARGE_IN_VERIFY` | Speech detected during agent turn; verifying if barge-in |
| `BARGE_IN_INTERRUPTED` | Barge-in confirmed; LLM/TTS cancelled |
| `DISCONNECTED` | Session teardown complete |

---

## Event Reference

| Event | Trigger |
|---|---|
| `SESSION_ADMITTED` | JWT verified, session config loaded |
| `VAD_SPEECH_START` | Silero VAD detects speech onset |
| `VAD_SPEECH_END` | Silero VAD detects end of speech |
| `STT_FINAL` | STT provider emits a final transcript |
| `LLM_FIRST_TOKEN` | LLM emits its first output token |
| `TOOL_CALL_START` | LLM emits a tool call request |
| `TOOL_RESULT` | Tool execution returned result |
| `TTS_FIRST_BYTE` | TTS provider emits first audio chunk |
| `TTS_DRAINED` | Client confirms server egress and scheduled playout are drained |
| `BARGE_CONFIRMED` | Barge-in verification engine confirms real speech |
| `BARGE_FALSE_ALARM` | Barge-in verification engine rejects as noise |
| `BARGE_VERIFY_TIMEOUT` | Barge verification window expired |
| `DISCONNECT` | Client WebSocket closed |
| `HANGUP` | PSTN call terminated |

---

## Session Startup Sequence

When a client connects to `/ws/audio`:

1. **JWT Verification** — `verify_session_jwt(token)` decodes and validates the signed JWT
2. **Session Config Load** — `_load_session_config()` reads tenant/compliance data from DB
3. **Provider Selection** — `orchestrator.apply_provider_selection(config)` swaps STT/LLM/TTS adapters
4. **FSM Admission** — `fsm.trigger(SESSION_ADMITTED)` transitions `CONNECTING → LISTENING`
5. **Gladia Live STT Socket** — One persistent Gladia WebSocket is opened for the entire call
6. **Greeting** (optional) — If `UCVE_INITIAL_GREETING` env var is set, it is queued as a synthetic user turn immediately

---

## Turn Lifecycle (Normal Path)

```
1. VAD speech_start → LISTENING → USER_SPEAKING
2. Mic audio buffered into speech_buffer + streamed to Gladia Live STT
3. Gladia emits final transcript → enqueue_voice_turn(text)
4. _turn_worker dequeues text → orchestrator.run_turn(config, text)
5. run_turn:
   a. RAG context retrieval (speculative + on-demand)
   b. LLM streaming (Groq / Gemini / OpenAI)
   c. Sentence chunking → TTS streaming per sentence
   d. PCM audio frames pushed to egress queue
   e. Egress sender loop drains queue → on_audio_out() → WS binary frame
6. Server drains egress and emits `audio_end`
7. Client renders all scheduled sources and emits `control.playback_drained`
8. `TTS_DRAINED` → `AGENT_SPEAKING` → `LISTENING`
```

---

## Barge-In Lifecycle

When the user speaks while the agent is playing audio:

```
VAD speech_start (during AGENT_SPEAKING)
    │
    ├─ Barge Verify ENABLED?
    │       │
    │       ├─ YES → BARGE_IN_VERIFY state
    │       │         50–250ms window checks VAD probability
    │       │         Sustained speech? → BARGE_CONFIRMED → execute_immediate_barge_in()
    │       │         Drops? → BARGE_FALSE_ALARM → resume playback
    │       │
    │       └─ NO → execute_immediate_barge_in() immediately
    │
    execute_immediate_barge_in():
        increment egress generation and pause the sender
        cancel and await turn, LLM, TTS, filler, and provider streams
        flush queued audio; reject a stale chunk already held by the sender
        notify client with control.barge_in then control.clear_audio
        client stops scheduled sources and returns control.clear_audio_ack
        commit only assistant words covered by acknowledged played PCM
        transition → BARGE_IN_INTERRUPTED
        begin new turn capture
```

---

## Session Teardown

On WebSocket disconnect or call hangup:

1. `stop` event is set — all worker tasks (`_ingress_worker`, `_turn_worker`, `_ping_loop`) are cancelled
2. Active turn tasks are cancelled gracefully
3. `orchestrator.finalize_session(config)` is called:
   - Emits final latency/usage metrics
   - Submits `CallRecord` to `PostCallPipeline` (async)
   - Cancels verification, LLM, TTS, filler, egress and live-STT tasks
   - Closes Gladia Live STT and pooled provider clients
   - Shuts down the shared VAD worker and clears pending playback state
4. `transport.close(websocket)` sends WS close frame

---

## Ping/Pong Keepalive

The worker node sends a JSON ping every **15 seconds** (configurable via `PING_INTERVAL_SEC`). If no pong is received within `15 * PONG_DEADLINE_MULTIPLIER` seconds, the connection is closed with code `1001` (Going Away).

Client must respond:
```json
{"event_type": "pong", "t": 1726123456.789}
```
