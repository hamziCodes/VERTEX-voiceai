# UCVE Production Voice Pipeline — Master Implementation Plan

**Status:** Planning document (not yet executed)  
**Scope:** Full real-time voice agent loop — listening, thinking, speaking, interruption, latency, and client playback  
**Target modules:** `core/`, `worker_raw/`, `examples/web-client/`, `tests/`  
**Legacy references:** `legacy_codebases/Multilingual_AI_Voice_Agent_gittracked`, `habiba-sdk-agent`, `AI_voice_agent_v3 - gemini`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Production Voice Agent — What "Done" Looks Like](#2-production-voice-agent--what-done-looks-like)
3. [End-to-End Architecture](#3-end-to-end-architecture)
4. [Current State vs Target State Matrix](#4-current-state-vs-target-state-matrix)
5. [Subsystem Deep Dives](#5-subsystem-deep-dives)
6. [Phased Implementation Roadmap](#6-phased-implementation-roadmap)
7. [File-by-File Change Registry](#7-file-by-file-change-registry)
8. [Configuration & Environment Contract](#8-configuration--environment-contract)
9. [Testing & Verification Strategy](#9-testing--verification-strategy)
10. [Rollout, Feature Flags & Risk Mitigation](#10-rollout-feature-flags--risk-mitigation)
11. [Legacy Harvest Index](#11-legacy-harvest-index)
12. [Glossary of Voice Agent Terms](#12-glossary-of-voice-agent-terms)

---

## 1. Executive Summary

This plan upgrades the UCVE real-time voice agent from a **functional demo pipeline** to a **production-grade conversational system**. It covers every layer of the voice loop:

| Layer | Subsystems |
|-------|-----------|
| **Ingress (Listen)** | Mic capture, frame slicing, noise gate, VAD, pre-speech buffer, speech capture, streaming STT |
| **Cognition (Think)** | RAG prefetch, LLM streaming, sentence chunking, tool/MCP execution, context management |
| **Egress (Speak)** | TTS synthesis, server egress queue, playback pause/resume, client jitter buffer, flush on barge-in |
| **Interruption** | Barge-in verify window, three-point cancel, interrupt buffer, ghost-chunk discard |
| **Turn-taking** | VAD endpointing, STT endpointing, serialized turn queue, FSM lifecycle |
| **Observability** | Latency waterfall, SLO budgets, client playback ack, debug telemetry |
| **Resilience** | Provider failover, mock modes, circuit breaker, HIPAA gate |
| **Telephony** | μ-law transcoding, SIP egress, shared pipeline contracts |

### Root cause of current demo failures

| Symptom | Root cause |
|---------|-----------|
| Repeated `[USER]: hello` loop | Mock STT returns fixed `"hello"` on every false VAD `speech_end`; VAD silence threshold ~96 ms + static energy gate |
| `AUDIO_IN 0 KB/sec` during agent speech | TTS egress may be queued but client playback or mock TTS chunking issue; separate from listening |
| Agent repeats "I heard you say: hello" | LLM mock/echo path + false STT triggers |
| Cough kills agent mid-sentence | Barge-in commits immediately — `BARGE_IN_VERIFY` FSM state never used in live path |
| Clipped first syllable | `_speech_buffer` cleared at `speech_start` — no 200 ms pre-roll |
| Queued audio plays after barge-in | `ThreePointCancel` flush callbacks not registered for `_egress_queue` |

### Strategy

Ship in **10 incremental phases**, each behind feature flags in `ListeningPipelineConfig` / `SpeakingPipelineConfig`. Default flags preserve current behavior until explicitly enabled per environment.

---

## 2. Production Voice Agent — What "Done" Looks Like

A production voice agent must satisfy this behavioral contract:

### 2.1 Session bootstrap

1. User connects (WebSocket or SIP).
2. Server admits session (`SESSION_ADMITTED` → `LISTENING`).
3. Agent plays greeting TTS (optional initial turn).
4. Client receives `session_ready` control event.
5. Mic ingress begins; server is in listen mode.

### 2.2 Normal turn (user speaks, agent responds)

1. User speaks → ingress slices audio into 512-sample frames.
2. Adaptive noise gate ignores room hum; Silero VAD detects onset after 100 ms hysteresis.
3. 200 ms pre-speech audio prepended to capture buffer.
4. Audio streams to Gladia Live WS; partial transcripts available.
5. User stops → VAD endpoint after 350–400 ms silence OR Gladia `endpointing=0.2`.
6. Final transcript dispatched to turn queue.
7. RAG reconcile (with speculative prefetch if partials were available).
8. LLM streams tokens; `SentenceChunker` emits 2-word first chunk for low TTFT.
9. TTS synthesizes per sentence; PCM streams to egress queue.
10. Client plays with 35 ms jitter prebuffer; reports `playback_started` for true e2e latency.
11. FSM: `USER_SPEAKING` → `PROCESSING_INFERENCE` → `AGENT_SPEAKING` → `LISTENING`.

### 2.3 Barge-in (user interrupts agent)

1. User speaks while agent audio is playing.
2. Server **pauses** egress immediately (does not cancel yet).
3. 700 ms verify window runs; sustained speech > 300 ms OR STT partial ≥ 3 words → commit.
4. On commit: three-point cancel (LLM task, TTS task, egress queue flush).
5. Client receives `barge_in` control event → flushes playback buffer, discards ghost chunks.
6. New user utterance captured and processed as fresh turn with interrupt context.
7. On false alarm (cough, desk tap): egress resumes; agent continues prior response.

### 2.4 Teardown

1. User disconnects or hangs up.
2. Active turns cancelled; post-call pipeline enqueued.
3. PHI redaction applied before persistence.
4. Usage metering recorded (`agent_sec`, `test_call_sec`).

---

## 3. End-to-End Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT (examples/web-client)                       │
│  Mic AudioWorklet → PCM16 16kHz → WS binary ingress                         │
│  WS binary egress → 35ms jitter buffer → WebAudio playback                  │
│  Control: set_prompt, text_turn, barge_in, playback_started, ping/pong       │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ WebSocket /ws/audio?token=JWT
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                    worker_raw/ws_session.py (WebSocketSessionRunner)         │
│  _receive_loop → FrameSlicer → inbound_mic queue → _ingress_worker          │
│  _turn_worker → run_turn (serialized, max 32 pending)                         │
│  _ping_loop → keepalive                                                       │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│              worker_raw/orchestration/pipeline.py (PipelineOrchestrator)      │
│                                                                               │
│  ┌─ LISTEN PATH ─────────────────────────────────────────────────────────┐  │
│  │ FrameSlicer → AdaptiveNoiseGate → SileroVADAdapter → PreSpeechBuffer   │  │
│  │ → SpeechCaptureBuffer → GladiaLiveSTT (partials + finals)              │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ THINK PATH ──────────────────────────────────────────────────────────┐  │
│  │ turn_queue → RAG SpeculativeRetrieval → GroqLLM stream                 │  │
│  │ → SentenceChunker → ToolOrchestrator (optional) → TextNormalizer       │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ SPEAK PATH ──────────────────────────────────────────────────────────┐  │
│  │ UpliftTTS stream → outbound_tts queue → _egress_sender_loop            │  │
│  │ → NativeWebSocketTransport.send_audio_frame → client playback          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ INTERRUPT PATH ──────────────────────────────────────────────────────┐  │
│  │ BargeVerifyEngine → pause_playback / resume_playback                   │  │
│  │ → BargeInController → ThreePointCancel → InterruptBuffer                 │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  SessionFSM: CONNECTING → LISTENING → USER_SPEAKING → PROCESSING_INFERENCE   │
│            → AGENT_SPEAKING → (BARGE_IN_VERIFY → BARGE_IN_INTERRUPTED)        │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Latency waterfall (per turn)

| Stage | Field | Target budget | Current wiring |
|-------|-------|---------------|----------------|
| VAD end-of-speech | `vad_end_of_speech_ms` | — | Set at turn start |
| STT final | `stt_final_ms` | 150 ms | Set immediately (batch STT already done) |
| RAG retrieve | `rag_retrieve_ms` | 100 ms | Wired |
| LLM TTFT | `llm_ttft_ms` | 200 ms | Wired |
| Chunker | `chunker_ms` | — | **Not populated** |
| TTS TTFB | `tts_ttfb_ms` | 150 ms | Wired |
| Client playback | `playback_start_ms` | — | Server emit only; **client ack missing** |
| E2E total | `total_e2e_ms` | p50 450 ms | Partial (no client ack) |

---

## 4. Current State vs Target State Matrix

### 4.1 Ingress / Listening

| Factor | Current (`core/` + `worker_raw/`) | Target (production) | Legacy reference |
|--------|-----------------------------------|---------------------|------------------|
| Frame slicing | Variable WS chunks fed to VAD | Strict 512-sample (1024 B) windows | v3 `SileroVADService.feed()` |
| VAD backend | Energy fallback (ONNX model missing) | Silero ONNX primary, energy fallback | All three legacy |
| Speech onset | 2 frames (~64 ms) | 3–4 frames (~100–128 ms) | habiba `VAD_START_SECS=0.1` |
| Speech endpoint | 3 silence frames (~96 ms) | 11–13 frames (~350–400 ms) | habiba `VAD_STOP_SECS=0.35` |
| Noise gate | Static -45 dB | Adaptive rolling RMS median | Multilingual `AdaptiveNoiseGate` |
| Pre-speech buffer | None (buffer cleared on onset) | 200 ms ring buffer prepended | New pattern (not in legacy) |
| STT mode | Batch REST on `speech_end` | Gladia Live WS + batch fallback | Multilingual/v3 `gladia_service.py` |
| STT partials | Not used | `receive_partial_transcripts=True` | Gladia `endpointing=0.2` |
| Mock STT | Always yields `"hello"` | Empty on short/false triggers | — |
| VAD CPU isolation | `asyncio.to_thread` per frame | Serialized executor queue | v3 `_vad_worker` |
| Ingress queue | `inbound_mic` drop-oldest 100 | Same (adequate) | Multilingual `AudioReceiver` |

### 4.2 Cognition / LLM

| Factor | Current | Target | Legacy reference |
|--------|---------|--------|------------------|
| LLM streaming | Groq SSE tokens | Same + tool_call chunks | habiba LiveKit agent |
| Sentence chunking | 2-word first chunk, sentence splits | Same + configurable via env | `core/language/chunker.py` |
| Tool calls | `tool:` prefix only (test) | Real `LLMStreamChunk.tool_calls` | habiba MCP tools |
| Tool filler audio | `ConversationalFillerSynth` exists, unwired | Speak filler after 400 ms tool latency | Multilingual comfort filler |
| RAG | `reconcile()` only at turn start | `speculate()` on partial STT + reconcile | `core/rag/speculative.py` |
| Context window | System prompt + single user turn | Multi-turn Redis history | Production standard |
| Text normalization | Post-stream only | Pre-TTS normalization | `core/language/normalizer.py` |
| FSM `LLM_FIRST_TOKEN` | Never fired | Fire on first token | — |

### 4.3 Egress / Speaking

| Factor | Current | Target | Legacy reference |
|--------|---------|--------|------------------|
| TTS provider | Uplift REST stream; mock tone | Same + chunk batching (8 KB yields) | v3 `uplift_service.py` pop-skip 2048 B |
| Server egress queue | `outbound_tts` BLOCK 200 | Same + flush on cancel | Multilingual `AudioSender` |
| Playback pause | None | `pause_playback()` / `resume_playback()` | Multilingual `AudioSender.pause()` |
| Egress flush on barge | Not wired | `register_flush_callback` clears queue | `ThreePointCancel` phase 04 tests |
| Resampling | `EgressResampler` exists, unused | Wire if TTS returns 24 kHz | `core/transport/resample_egress.py` |
| Client jitter buffer | 35 ms prebuffer, 20 ms chunks | Same + `PREBUFFER_CHUNKS=3` option | v3 `index.html` |
| Client barge flush | No `barge_in` handler | Flush worklet buffer on control event | v3 `bargeInActive` ghost discard |
| Client playback ack | Not sent | `playback_started` control event | `core/latency/playback.py` |
| `AUDIO_IN` metric | Shows 0 KB/sec | Reflect actual egress throughput | Demo console metric calc |

### 4.4 Interruption / Barge-in

| Factor | Current | Target | Legacy reference |
|--------|---------|--------|------------------|
| Verify window | Config exists (700 ms); bypassed | Live pause-verify-commit | Multilingual `_run_verification_window` |
| Sustained speech | 300 ms threshold in config | Measured from VAD during verify | Multilingual |
| Text backup barge | 3-word threshold in config | STT partial word count during playback | Multilingual L370–378 |
| Interrupt buffer | `InterruptBuffer` never fed | `buffer_partial` / `buffer_final` from STT | — |
| Reentrancy guard | Config flag, not enforced | Ignore duplicate `speech_start` in verify | — |
| FSM `BARGE_IN_VERIFY` | Defined, bypassed | Active during verify window | `core/fsm/session_fsm.py` |

### 4.5 Turn-taking & Session

| Factor | Current | Target |
|--------|---------|--------|
| Turn serialization | `_turn_queue` BLOCK 32 | Same (correct for v1) |
| Empty STT recovery | `resume_listening()` | Same + VAD reset |
| Greeting on connect | Not automatic | Optional `initial_greeting` in session config |
| Concurrent turns | One active turn per session | Same |
| Language profiles | `vad_silence_override_ms` in registry, unused | Wire per-language VAD overrides |

### 4.6 Observability & Compliance

| Factor | Current | Target |
|--------|---------|--------|
| Latency SLO | Warn-only p50 450 ms | Same + optional demotion |
| Client e2e latency | Missing | `PlaybackMetricHandler` wired |
| Debug VAD telemetry | None | Optional `UCVE_DEBUG_LISTENING=1` metrics |
| Live redaction | Post-call only | Optional live transcript redaction for HIPAA |
| Audit trail | Session teardown | Same |

### 4.7 Telephony

| Factor | Current | Target |
|--------|---------|--------|
| SIP ingress | μ-law → 16 kHz rebuffer | Same |
| SIP egress | Stubbed (`send_audio` pass) | Wire TTS → μ-law → SIP |
| Shared pipeline | VAD only, no turn loop | Full `PipelineOrchestrator` integration |

---

## 5. Subsystem Deep Dives

### 5.1 Audio ingress & frame slicing

**Purpose:** Normalize arbitrary WebSocket chunk sizes into canonical 32 ms frames required by Silero VAD.

**Current code:**
- `worker_raw/ws_session.py` `_receive_loop` — passes raw `pcm_data` directly to `AudioFrame`
- `core/types/constants.py` — `FRAME_SAMPLES=512`, `FRAME_BYTES=1024`
- `core/vad/silero_adapter.py` — expects single frame, no internal accumulator

**Target implementation:**
- New `core/listening/frame_slicer.py` — `FrameSlicer.push(chunk) → list[bytes]`
- Insert in `_receive_loop` before `_ingress_queue.put()`
- Belt-and-suspenders: internal `_byte_buffer` in `SileroVADAdapter` as secondary guard

**Acceptance criteria:**
- 500 B + 600 B WS messages → exactly one 1024 B frame + 76 B held
- Zero ONNX dimension errors in logs

---

### 5.2 Adaptive noise gate

**Purpose:** Prevent ambient room noise (fans, AC, keyboard idle hum) from triggering VAD.

**Current code:**
- `SileroVADAdapter.energy_threshold_db = -45.0` (static)
- No RMS baseline tracking

**Target implementation:**
- New `core/listening/noise_gate.py` — port `AdaptiveNoiseGate` from Multilingual
- Parameters: `k=3.0`, `window=50`, `default_floor=0.015`
- Two-stage gate: RMS check → only then Silero inference
- Floor updates only during silence (`not agent_speaking and not user_speaking`)

**Acceptance criteria:**
- 10 s fan noise → zero `speech_start` events
- Normal speech 15 dB above floor → passes gate

---

### 5.3 VAD — Silero + hysteresis

**Purpose:** Accurate, low-latency speech/silence detection with conversational timing.

**Current code (`core/vad/silero_adapter.py`):**
```python
_min_speech_frames = 2      # ~64 ms
_min_silence_frames = 3     # ~96 ms — TOO SHORT
```

**Target timing (from habiba ADRs + v3 config):**

| Parameter | Value | Frames @ 32 ms |
|-----------|-------|----------------|
| `min_speech_duration_ms` | 100 | 4 |
| `min_silence_duration_ms` | 380 | 12 |
| `threshold` | 0.5 | — |

**Target hysteresis logic:**
- Separate `_onset_frames` and `_silence_frames` counters
- `speech_start` only after N consecutive speech frames while not speaking
- `speech_end` only after M consecutive silence frames while speaking
- Hangover is implicit in silence counter (not a separate effective_speech OR)

**ONNX model:**
- Add `core/vad/models/silero_vad.onnx`
- Document download in `docs/developer/TROUBLESHOOTING.md`
- `torch.set_num_threads(1)` at module init if torch available

**Acceptance criteria:**
- Natural pause "hello ... how are you" → single utterance, one `speech_end`
- Keyboard click → no `speech_start`

---

### 5.4 Pre-speech ring buffer

**Purpose:** Capture audio before VAD onset to avoid clipping first consonants ("Hello" → "ello").

**Current code (`pipeline.py` line ~177):**
```python
if not self._capturing_speech:
    self._speech_buffer = bytearray()  # DESTROYS pre-onset audio
```

**Target implementation:**
- New `core/listening/pre_speech_buffer.py`
- Capacity: 200 ms × 16 kHz × 2 bytes = 6400 bytes
- `push()` on every frame regardless of capture state
- `flush_to(target)` on `speech_start` before appending live frames

**Acceptance criteria:**
- Waveform inspection shows 200 ms pre-roll before first detected speech frame

---

### 5.5 Speech capture & STT dispatch

**Purpose:** Accumulate user audio and dispatch to STT (streaming preferred, batch fallback).

**Current path:**
1. `_capturing_speech` flag + `_speech_buffer` bytearray (max 512 KB)
2. `speech_end` → `_speech_end_pending` → `transcribe_speech_buffer()`
3. `GladiaSTTProvider` — REST `/v2/pre-recorded`; mock yields `"hello"`

**Target streaming path:**
- New `core/providers/adapters/gladia_live_stt.py`
- Init: `model=solaria-1`, `endpointing=0.2`, `receive_partial_transcripts=True`
- Dual async loops: send audio / receive transcripts
- Partials → `barge_in_controller.buffer_partial(text)`
- Finals → `_turn_queue.put((text, None))`
- Local VAD `speech_end` as backup endpoint if WS drops

**Mock STT fix (immediate):**
```python
# gladia_stt.py — mock mode
if len(buf) < _MIN_PCM_BYTES:
    return  # yield nothing
# mock_text="" by default; tests opt in
```

**Acceptance criteria:**
- One intentional utterance → one `[USER]` transcript
- Partial transcripts visible in debug mode within 200 ms of speech

---

### 5.6 LLM streaming & sentence chunking

**Purpose:** Minimize time-to-first-audio by pipelining LLM tokens into TTS sentences.

**Current code:**
- `core/language/chunker.py` — `SentenceChunker.chunk()`: 2-word first chunk, then sentence splits
- `pipeline.py` `run_turn()` — `stream_buffer` accumulates tokens; TTS starts on first sentence

**Target enhancements:**
1. Stamp `waterfall.chunker_ms` when first chunk emitted
2. Fire `SessionEvent.LLM_FIRST_TOKEN` on first token
3. Configurable `first_chunk_words` / `min_chunk_words` via env
4. Wire `LLMStreamChunk.tool_calls` from Groq adapter
5. On tool call: FSM `TOOL_CALL_START` → `ToolOrchestrator` → `TOOL_RESULT` → resume LLM

**Acceptance criteria:**
- First TTS audio within 500 ms of STT final (with live providers)
- Tool call round-trip completes without dead air (filler audio optional)

---

### 5.7 TTS synthesis & server egress

**Purpose:** Stream natural agent speech to client with backpressure and cancel support.

**Current code:**
- `UpliftTTSProvider.synthesize_stream()` — mock tone PCM chunked at 3200 B
- `_emit_audio()` → `_egress_queue` (BLOCK 200) → `_egress_sender_loop` → `on_audio_out`
- `ThreePointCancel` cancels LLM/TTS tasks but **does not flush egress queue**

**Target enhancements:**

1. **Egress flush on cancel:**
   ```python
   def _flush_egress_queue():
       while not self._egress_queue.empty():
           try: self._egress_queue.get_nowait()
           except: break
   self.three_point_cancel.register_flush_callback(_flush_egress_queue)
   ```

2. **Playback pause/resume (barge verify):**
   ```python
   async def _egress_sender_loop(self):
       pcm = await self._egress_queue.get()
       await self._playback_pause_event.wait()  # blocks during verify
       await self.on_audio_out(pcm)
   ```

3. **TTS output batching (from v3):**
   - Pop-skip first 2048 B per turn (codec priming)
   - Yield in 8192 B chunks for smoother WS throughput

4. **Wire `EgressResampler`** if Uplift returns 24 kHz

**Acceptance criteria:**
- `AUDIO_IN` metric shows non-zero KB/sec during agent speech
- After barge-in commit, zero additional agent audio plays
- After false-alarm barge, agent audio resumes

---

### 5.8 Client playback & jitter buffer

**Purpose:** Gapless, low-latency audio playback with clean barge-in flush.

**Current code (`examples/web-client/index.html`):**
- `playTime` scheduler with 35 ms jitter prebuffer
- 320-sample (20 ms) playback chunks
- 40 ms trailing `flushPcmQueue`
- No `barge_in` control handler
- No `playback_started` metric to server

**Target enhancements:**

1. **Barge-in flush:**
   ```javascript
   if (event_type === 'barge_in') {
     bargeInActive = true;
     playTime = 0;
     pcmQueue = [];
     // send cancel ack
   }
   // On binary frame: if (bargeInActive) return; // ghost chunk discard
   ```

2. **Playback started ack:**
   ```javascript
   // On first src.start():
   ws.send(JSON.stringify({ event_type: 'metric', payload: { kind: 'playback_started', t: Date.now() }}));
   ```

3. **Optional `PREBUFFER_CHUNKS=3`** (~96 ms) for high-jitter networks

4. **Mic framing:** Ensure AudioWorklet emits 512-sample aligned chunks (verify `pcm-worklet.js`)

**Acceptance criteria:**
- No overlapping agent audio after barge-in
- Server `playback_start_ms` reflects client ack (true e2e latency)

---

### 5.9 Barge-in — pause, verify, commit

**Purpose:** Production interrupt behavior — don't kill agent on coughs.

**Current code (`pipeline.py` `process_frame_async`):**
```python
if self.fsm.state == SessionState.AGENT_SPEAKING:
    result = self.barge_in_controller._commit_barge_in(...)  # IMMEDIATE
    self.three_point_cancel.execute_cancel_and_flush()
```

**FSM already supports verify** (`core/fsm/session_fsm.py`):
- `AGENT_SPEAKING` + `VAD_SPEECH_START` → `BARGE_IN_VERIFY`
- `BARGE_IN_VERIFY` + `BARGE_CONFIRMED` → `BARGE_IN_INTERRUPTED`
- `BARGE_IN_VERIFY` + `BARGE_FALSE_ALARM` → `AGENT_SPEAKING`

**Target implementation:**
- New `core/listening/barge_verify.py` — `BargeVerifyEngine`
- Step A: `pause_playback()` + FSM → `BARGE_IN_VERIFY`
- Step B: `asyncio.sleep(verify_window_ms / 1000)`
- Step C: Check `sustained_speech_ms >= 300` OR `vad.is_speaking` OR `stt_partial_words >= 3`
- Step D commit: `_commit_barge_in()` + `execute_cancel_and_flush()` + client `barge_in` event
- Step C false alarm: `_false_alarm()` + `resume_playback()`

**Acceptance criteria:**
- Cough during agent speech → agent resumes within 800 ms
- "Stop wait" during agent speech → agent stops, new turn processes

---

### 5.10 Turn-taking & FSM lifecycle

**Full FSM path (target):**

```
CONNECTING
  └─ SESSION_ADMITTED → LISTENING
LISTENING
  └─ VAD_SPEECH_START → USER_SPEAKING
  └─ STT_FINAL → PROCESSING_INFERENCE
USER_SPEAKING
  └─ VAD_SPEECH_END → PROCESSING_INFERENCE
PROCESSING_INFERENCE
  └─ TTS_FIRST_BYTE → AGENT_SPEAKING
  └─ TOOL_CALL_START → TOOL_EXECUTING
AGENT_SPEAKING
  └─ TTS_DRAINED → LISTENING
  └─ VAD_SPEECH_START → BARGE_IN_VERIFY
BARGE_IN_VERIFY
  └─ BARGE_CONFIRMED → BARGE_IN_INTERRUPTED
  └─ BARGE_FALSE_ALARM → AGENT_SPEAKING
BARGE_IN_INTERRUPTED
  └─ VAD_SPEECH_END → PROCESSING_INFERENCE
```

**Turn queue:** `_turn_queue` maxsize=32, BLOCK — prevents unbounded backlog.

---

### 5.11 Latency & SLO

**Wire missing waterfall stages:**

| Action | File |
|--------|------|
| Stamp `chunker_ms` | `pipeline.py` on first `SentenceChunker` output |
| Fire `LLM_FIRST_TOKEN` | `pipeline.py` on first LLM token |
| Client `playback_started` | `ws_session.py` handle control event → `PlaybackMetricHandler` |
| VAD end timestamp | Set at actual `speech_end`, not turn start |

**SLO targets (`core/latency/slo_policy.py`):**
- E2E p50: 450 ms
- E2E p95: 850 ms
- Per-stage budgets in `DEFAULT_STAGE_BUDGETS`

---

### 5.12 Cancellation contract

**Three-point cancel (`core/fsm/cancel_contract.py`):**
1. **Producer:** Cancel LLM/TTS asyncio tasks
2. **Sender:** Flush `_egress_queue` via registered callback
3. **Transport:** Client `barge_in` event → flush playback buffer

**Per-turn reset:** New `AsyncioCancellationToken` instances; `three_point_cancel.reset()`.

**Must wire in `PipelineOrchestrator.__init__` or `attach_ws_session`:**
```python
self.three_point_cancel.register_flush_callback(self._flush_egress_queue)
```

---

### 5.13 RAG speculative retrieval

**Current:** Only `reconcile(user_text)` at turn start.

**Target:**
```python
# On STT partial:
await self.speculative_rag.speculate(partial_text, tenant_id)
# On STT final:
rag_chunks = await self.speculative_rag.reconcile(final_text, tenant_id)
```

Requires streaming STT (Phase 5). Saves 50–150 ms on RAG-heavy turns.

---

### 5.14 Provider resilience

| Mechanism | File | Status |
|-----------|------|--------|
| Mock mode | All adapters | `RUN_LIVE_PROVIDERS!=1` |
| Failover router | `core/providers/failover.py` | Wired for LLM/TTS |
| Circuit breaker | `FailoverRouter` | 3.5 s first-chunk timeout |
| Null providers | `null_*.py` | Fallback after chain failure |
| Chain resolver | `core/providers/chain_resolver.py` | **Not wired** — future per-agent chains |

---

### 5.15 Telephony path

**Current:** `InboundTelephonySessionHandler` → μ-law decode → `process_frame()` (VAD only).

**Target:** Share full `PipelineOrchestrator` with SIP egress:
1. Wire `TelnyxDirectSIPAdapter.send_audio()` to TTS output
2. μ-law encode outbound 16 kHz → 8 kHz
3. Reuse `SpeechCaptureEngine` and barge-in logic

---

## 6. Phased Implementation Roadmap

### Phase 0 — Foundation & Quick Wins
**Duration:** 1 day | **Risk:** None

| Step | Action | File(s) |
|------|--------|---------|
| 0.1 | Create `core/listening/config.py` — `ListeningPipelineConfig`, `SpeakingPipelineConfig` | NEW |
| 0.2 | Create `core/listening/__init__.py` | NEW |
| 0.3 | Add env vars to `.env.example` | `.env.example` |
| 0.4 | **Quick win:** `_min_silence_frames=12`, `_min_speech_frames=4` | `silero_adapter.py` |
| 0.5 | **Quick win:** Mock STT yields empty on short buffer | `gladia_stt.py` |
| 0.6 | **Quick win:** Don't clear speech buffer on onset | `pipeline.py` |
| 0.7 | Wire `register_flush_callback` for egress queue | `pipeline.py` |

**Flag:** `UCVE_PIPELINE_V2=quick_wins`  
**Validation:** No more "hello" loop in 10 s silence test

---

### Phase 1 — Frame Slicing & VAD Hysteresis
**Duration:** 2–3 days | **Risk:** Low

| Step | Action | File(s) |
|------|--------|---------|
| 1.1 | Implement `FrameSlicer` | `core/listening/frame_slicer.py` |
| 1.2 | Insert slicer in WS receive loop | `ws_session.py` |
| 1.3 | Refactor VAD dual-counter hysteresis | `silero_adapter.py` |
| 1.4 | Extend `VADConfig` with timing fields | `core/providers/interfaces/vad.py` |
| 1.5 | Add `silero_vad.onnx` model + download script | `core/vad/models/` |
| 1.6 | Unit tests | `tests/listening/test_frame_slicer.py`, `test_vad_hysteresis.py` |

**Flag:** `UCVE_PIPELINE_V2=frame_slicing,vad_timing`  
**Validation:** One utterance → one transcript; phase 17 tests green

---

### Phase 2 — Adaptive Noise Gate
**Duration:** 1–2 days | **Risk:** Low

| Step | Action | File(s) |
|------|--------|---------|
| 2.1 | Port `AdaptiveNoiseGate` | `core/listening/noise_gate.py` |
| 2.2 | Create `SpeechCaptureEngine` orchestrator | `core/listening/speech_capture.py` |
| 2.3 | Two-stage gate in VAD path | `silero_adapter.py`, `speech_capture.py` |
| 2.4 | Pass `agent_speaking` flag from FSM | `pipeline.py` |
| 2.5 | Unit tests | `tests/listening/test_noise_gate.py` |

**Flag:** `+noise_gate`  
**Validation:** Fan noise 10 s → zero false triggers

---

### Phase 3 — Pre-Speech Ring Buffer
**Duration:** 1 day | **Risk:** Low

| Step | Action | File(s) |
|------|--------|---------|
| 3.1 | Implement `PreSpeechRingBuffer` | `core/listening/pre_speech_buffer.py` |
| 3.2 | Wire into `SpeechCaptureEngine` | `speech_capture.py` |
| 3.3 | Replace buffer clear with `flush_to()` | `pipeline.py` |
| 3.4 | Unit tests | `tests/listening/test_pre_speech_buffer.py` |

**Flag:** `+pre_roll`  
**Validation:** First syllable not clipped in waveform inspection

---

### Phase 4 — Smart Barge-In (Pause & Verify)
**Duration:** 3–4 days | **Risk:** Medium

| Step | Action | File(s) |
|------|--------|---------|
| 4.1 | Implement `BargeVerifyEngine` | `core/listening/barge_verify.py` |
| 4.2 | Add `pause_playback()` / `resume_playback()` | `pipeline.py` |
| 4.3 | Replace immediate commit with verify flow | `pipeline.py` `process_frame_async` |
| 4.4 | Enforce reentrancy guard | `barge_verify.py` |
| 4.5 | Send client `barge_in` control event on commit | `pipeline.py` / `ws_session.py` |
| 4.6 | Extend phase 04 tests for live wiring | `test_phase_04_barge_in.py` |
| 4.7 | Integration tests | `tests/listening/test_barge_verify_live.py` |

**Flag:** `+barge_verify`  
**Validation:** Cough → resume; sustained speech → commit

---

### Phase 5 — Gladia Live Streaming STT
**Duration:** 4–5 days | **Risk:** High

| Step | Action | File(s) |
|------|--------|---------|
| 5.1 | Implement `GladiaLiveSTTSession` | `core/providers/adapters/gladia_live_stt.py` |
| 5.2 | Dual-loop send/receive architecture | same |
| 5.3 | Wire partials to `buffer_partial` | `pipeline.py` |
| 5.4 | Wire finals to turn queue | `pipeline.py`, `ws_session.py` |
| 5.5 | Keep REST batch as fallback | `gladia_stt.py` |
| 5.6 | Connection lifecycle (connect on speech_start, close on speech_end) | `pipeline.py` |
| 5.7 | Integration tests with mock WS server | `tests/listening/test_gladia_live_stt.py` |

**Flag:** `+streaming_stt` (requires `GLADIA_API_KEY` + `RUN_LIVE_PROVIDERS=1`)  
**Validation:** Partial transcripts in debug mode; <200 ms STT latency improvement

---

### Phase 6 — Speaking / Egress Hardening
**Duration:** 2–3 days | **Risk:** Medium

| Step | Action | File(s) |
|------|--------|---------|
| 6.1 | TTS output batching (8 KB chunks, pop-skip 2048 B) | `uplift_tts.py` |
| 6.2 | Wire `EgressResampler` if needed | `pipeline.py` |
| 6.3 | Create `SpeakingPipelineConfig` | `core/listening/config.py` |
| 6.4 | Fix `AUDIO_IN` metric calculation | `examples/web-client/index.html` |
| 6.5 | Client barge-in flush handler | `index.html` |
| 6.6 | Client `playback_started` ack | `index.html`, `ws_session.py` |
| 6.7 | Optional `PREBUFFER_CHUNKS` config | `index.html` |

**Flag:** `+speaking_hardening`  
**Validation:** Audible agent output; non-zero AUDIO_IN; clean barge flush

---

### Phase 7 — LLM & Tool Loop
**Duration:** 3–4 days | **Risk:** Medium

| Step | Action | File(s) |
|------|--------|---------|
| 7.1 | Parse `tool_calls` from Groq stream | `groq_llm.py` |
| 7.2 | Wire tool call detection in `run_turn` | `pipeline.py` |
| 7.3 | Fire `LLM_FIRST_TOKEN` FSM event | `pipeline.py` |
| 7.4 | Stamp `chunker_ms` in waterfall | `pipeline.py` |
| 7.5 | Wire `ConversationalFillerSynth` for tool latency | `pipeline.py` |
| 7.6 | Multi-turn Redis history in LLM messages | `pipeline.py` |
| 7.7 | Tests | `tests/listening/test_tool_loop.py` |

**Flag:** `+tool_loop`  
**Validation:** LLM tool call → tool execution → spoken result

---

### Phase 8 — RAG Speculative Prefetch
**Duration:** 1–2 days | **Risk:** Low (depends on Phase 5)

| Step | Action | File(s) |
|------|--------|---------|
| 8.1 | Call `speculate()` on STT partials | `pipeline.py` |
| 8.2 | Call `reconcile()` on STT final | `pipeline.py` |
| 8.3 | Stamp accurate `rag_retrieve_ms` | `pipeline.py` |
| 8.4 | Tests | extend `test_phase_23_realtime_rag.py` |

**Flag:** `+rag_speculative`  
**Validation:** RAG retrieve ms near zero on cache hit

---

### Phase 9 — VAD Worker Queue & CPU Isolation
**Duration:** 1–2 days | **Risk:** Low

| Step | Action | File(s) |
|------|--------|---------|
| 9.1 | Implement `VADWorker` serialized queue | `core/listening/vad_worker.py` |
| 9.2 | Use `vad_internal` queue policy | `ws_session.py` |
| 9.3 | `run_in_executor` with `max_workers=1` | `vad_worker.py` |
| 9.4 | Load test: 10 concurrent sessions | `tests/performance/` |

**Flag:** `+vad_worker`  
**Validation:** Event loop lag < 5 ms under load

---

### Phase 10 — Telephony, Observability & Production Hardening
**Duration:** 3–5 days | **Risk:** Medium

| Step | Action | File(s) |
|------|--------|---------|
| 10.1 | Wire SIP TTS egress | `telnyx_direct_sip.py`, `inbound_handler.py` |
| 10.2 | Shared `SpeechCaptureEngine` for telephony | `inbound_handler.py` |
| 10.3 | Debug VAD telemetry (`UCVE_DEBUG_LISTENING=1`) | `pipeline.py` |
| 10.4 | Wire `PlaybackMetricHandler` | `ws_session.py`, `core/latency/playback.py` |
| 10.5 | Per-language VAD overrides from registry | `speech_capture.py`, `core/language/registry.py` |
| 10.6 | Optional live transcript redaction (HIPAA) | `pipeline.py` |
| 10.7 | Initial greeting on session start | `ws_session.py`, `session_config.py` |
| 10.8 | E2E sovereign conversation test update | `tests/e2e/scenarios/sovereign_conversation.py` |
| 10.9 | Runbook documentation | `docs/runbooks/voice-pipeline-tuning.md` |

**Flag:** `+production`  
**Validation:** Full manual checklist (Section 9.3) passes

---

## 7. File-by-File Change Registry

### New files

| Path | Phase | Purpose |
|------|-------|---------|
| `core/listening/__init__.py` | 0 | Package init |
| `core/listening/config.py` | 0 | Pipeline config dataclasses |
| `core/listening/frame_slicer.py` | 1 | 512-sample byte accumulator |
| `core/listening/noise_gate.py` | 2 | AdaptiveNoiseGate |
| `core/listening/pre_speech_buffer.py` | 3 | 200 ms ring buffer |
| `core/listening/speech_capture.py` | 2–3 | Gate + VAD + pre-roll orchestrator |
| `core/listening/barge_verify.py` | 4 | Pause-verify-commit engine |
| `core/listening/vad_worker.py` | 9 | Serialized VAD inference queue |
| `core/providers/adapters/gladia_live_stt.py` | 5 | Gladia Live WebSocket STT |
| `core/vad/models/silero_vad.onnx` | 1 | Silero ONNX model |
| `tests/listening/test_*.py` | 1–5 | Unit/integration tests |
| `docs/runbooks/voice-pipeline-tuning.md` | 10 | Operations runbook |

### Modified files

| Path | Phases | Changes |
|------|--------|---------|
| `core/vad/silero_adapter.py` | 0–2 | Hysteresis, frame buffer, noise gate hook |
| `core/providers/interfaces/vad.py` | 1 | Extended VADConfig |
| `core/providers/adapters/gladia_stt.py` | 0, 5 | Mock fix, Live WS delegate |
| `core/providers/adapters/groq_llm.py` | 7 | Tool call parsing |
| `core/providers/adapters/uplift_tts.py` | 6 | Output batching |
| `core/fsm/barge_in.py` | 4 | Public async verify entry point |
| `worker_raw/orchestration/pipeline.py` | 0–8 | Major refactor — speech capture, barge, egress |
| `worker_raw/ws_session.py` | 1, 6, 10 | Frame slicer, playback ack, greeting |
| `worker_raw/orchestration/session_config.py` | 10 | `initial_greeting` field |
| `worker_raw/main.py` | 0 | Load pipeline config from env |
| `examples/web-client/index.html` | 6 | Barge flush, playback ack, metric fix |
| `examples/web-client/pcm-worklet.js` | 6 | 512-sample mic alignment |
| `.env.example` | 0 | Pipeline tuning env vars |
| `telephony_gateway/adapters/telnyx_direct_sip.py` | 10 | SIP egress |
| `worker_raw/telephony/inbound_handler.py` | 10 | Full pipeline integration |

### Do NOT modify

| Path | Reason |
|------|--------|
| `core/fsm/session_fsm.py` TRANSITION_TABLE | Already correct |
| `legacy_codebases/` | Read-only harvest |
| `docs/blueprint/` | Read-only reference |
| `control-plane/` | Out of scope (mint/auth works) |

---

## 8. Configuration & Environment Contract

### 8.1 Master feature flag

```bash
# Comma-separated enabled phases (default: empty = legacy behavior)
UCVE_PIPELINE_V2=quick_wins,frame_slicing,vad_timing,noise_gate,pre_roll,barge_verify,streaming_stt,speaking_hardening,tool_loop,rag_speculative,vad_worker,production
```

### 8.2 VAD tuning

```bash
UCVE_VAD_THRESHOLD=0.5
UCVE_VAD_MIN_SPEECH_MS=100
UCVE_VAD_MIN_SILENCE_MS=380
UCVE_VAD_PRE_SPEECH_MS=200
UCVE_NOISE_GATE_K=3.0
UCVE_NOISE_GATE_WINDOW=50
UCVE_NOISE_GATE_DEFAULT_FLOOR=0.015
```

### 8.3 Barge-in tuning

```bash
UCVE_BARGE_VERIFY_WINDOW_MS=700
UCVE_BARGE_MIN_SUSTAINED_SPEECH_MS=300
UCVE_BARGE_TEXT_BACKUP_WORDS=3
```

### 8.4 STT tuning

```bash
UCVE_GLADIA_ENDPOINTING=0.2
UCVE_GLADIA_RECEIVE_PARTIALS=true
UCVE_STT_MOCK_TEXT=          # empty = no mock text on false triggers
```

### 8.5 Speaking / TTS tuning

```bash
UCVE_TTS_CHUNK_SIZE_BYTES=8192
UCVE_TTS_POP_SKIP_BYTES=2048
UCVE_EGRESS_PREBUFFER_MS=35
UCVE_CLIENT_PREBUFFER_CHUNKS=3
```

### 8.6 LLM / chunking tuning

```bash
UCVE_CHUNKER_FIRST_WORDS=2
UCVE_CHUNKER_MIN_WORDS=3
UCVE_TOOL_FILLER_DELAY_MS=400
```

### 8.7 Observability

```bash
UCVE_DEBUG_LISTENING=0       # 1 = emit per-frame VAD metrics to client
UCVE_DEBUG_LATENCY=0         # 1 = log waterfall per turn
```

### 8.8 Provider modes (existing)

```bash
RUN_LIVE_PROVIDERS=0         # 1 = real STT/LLM/TTS
RUN_MOCK_PROVIDERS=0         # 1 = force mock even with keys
PLATFORM_GLADIA_API_KEY=
PLATFORM_GROQ_API_KEY=
PLATFORM_UPLIFT_API_KEY=
```

---

## 9. Testing & Verification Strategy

### 9.1 Automated test matrix

| Phase | Test command | Pass threshold |
|-------|-------------|----------------|
| 0 | `pytest tests/listening/ -v` | All new tests pass |
| 0 | `pytest voice_engine_plan/tests/phase_tests/test_phase_04_barge_in.py -v` | 0 failures |
| 1 | `pytest tests/listening/test_frame_slicer.py tests/listening/test_vad_hysteresis.py -v` | 0 failures |
| 1 | `pytest voice_engine_plan/tests/phase_tests/test_phase_17_pipeline_integration.py -v` | 0 failures |
| 4 | `pytest tests/listening/test_barge_verify_live.py -v` | 0 failures |
| 5 | `pytest tests/listening/test_gladia_live_stt.py -v` | 0 failures |
| All | `pytest tests/hardening/test_h5_pipeline_e2e.py -v` | 0 failures |
| All | `pytest tests/e2e/scenarios/sovereign_conversation.py -v` | 0 failures |

### 9.2 Unit test specifications

#### `test_frame_slicer.py`
- Empty input → no frames
- Exactly 1024 B → one frame, buffer empty
- 1024 + 500 B → one frame, 500 B held
- 5000 B → four frames, 976 B held

#### `test_vad_hysteresis.py`
- 3 speech frames → no `speech_start`
- 4 speech frames → `speech_start=True`
- 11 silence frames while speaking → no `speech_end`
- 12 silence frames while speaking → `speech_end=True`

#### `test_noise_gate.py`
- 50 low-RMS frames → floor stabilizes
- RMS below `floor * k` → gate blocks
- RMS above `floor * k` → gate passes
- Floor frozen when `agent_speaking=True`

#### `test_pre_speech_buffer.py`
- Push 300 ms → flush returns last 200 ms
- Capacity never exceeds 6400 B

#### `test_barge_verify_live.py`
- Agent speaking + 200 ms noise → resume (no cancel)
- Agent speaking + 400 ms speech → commit (cancel tasks)
- Agent speaking + STT partial 4 words → commit

### 9.3 Manual verification checklist (Developer Console)

| # | Step | Pass criteria |
|---|------|---------------|
| 1 | Start session | `session_ready` event; optional greeting plays |
| 2 | Stay silent 15 s | **Zero** `[USER]` transcripts |
| 3 | Say "hello, how are you today?" with natural pauses | **One** `[USER]` transcript, full sentence |
| 4 | Wait for agent response | `AUDIO_IN` > 0 KB/sec; audible output |
| 5 | Cough during agent speech | Agent **resumes** (Phase 4+) |
| 6 | Say "wait stop" during agent speech | Agent **stops**; new turn with interrupt text |
| 7 | Check latency debug | `llm_ttft_ms`, `tts_ttfb_ms` populated |
| 8 | End session | Clean WS close; no orphan tasks in logs |

### 9.4 Regression gates (every phase)

```bash
python voice_engine_plan/scripts/verify_plan_integrity.py
python -m pytest voice_engine_plan/tests/phase_tests/ -v --tb=short
python -m pytest tests/hardening/ -v --tb=short
```

---

## 10. Rollout, Feature Flags & Risk Mitigation

### 10.1 Recommended rollout sequence

| Week | Phases | Environment | Success metric |
|------|--------|-------------|----------------|
| 1 | 0 + 1 | Dev | No hello loop |
| 2 | 2 + 3 | Dev | Clean capture in noisy room |
| 3 | 4 + 6 | Staging | Barge-in works; audible output |
| 4 | 5 | Staging (live keys) | Streaming STT partials |
| 5 | 7 + 8 | Staging | Tool loop + RAG prefetch |
| 6 | 9 + 10 | Production | Full checklist passes |

### 10.2 Risk matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Silero ONNX missing | Medium | Medium | Energy fallback with corrected timing still fixes 80% |
| Gladia Live WS drops | Medium | High | Auto-reconnect + REST batch fallback on `speech_end` |
| Barge verify adds 700 ms to real interrupts | Low | Medium | Only during `AGENT_SPEAKING`; listening unaffected |
| Breaking existing phase tests | Medium | High | Feature flags default off; run full suite each phase |
| Client playback out of sync | Medium | Medium | `barge_in` flush + ghost chunk discard |
| Telephony regression | Low | Medium | Telephony is Phase 10; WS path validated first |

### 10.3 Rollback procedure

1. Set `UCVE_PIPELINE_V2=` (empty) in `.env`
2. Restart `worker_raw` uvicorn process
3. Legacy code paths activate immediately (no code deploy needed if flags are env-only)

---

## 11. Legacy Harvest Index

| Pattern | Source file | Target UCVE file |
|---------|------------|------------------|
| `AdaptiveNoiseGate` | `Multilingual_.../vad_service.py` L98–117 | `core/listening/noise_gate.py` |
| Two-stage Silero gate | `Multilingual_.../vad_service.py` L311–327 | `speech_capture.py` |
| Barge verify window | `Multilingual_.../session.py` L249–292 | `barge_verify.py` |
| `AudioSender.pause/resume` | `Multilingual_.../audio_sender.py` L121–129 | `pipeline.py` |
| Byte-buffer frame slicer | `v3/.../silero_service.py` L77–91 | `frame_slicer.py` |
| VAD worker queue | `v3/.../websocket.py` L336–367 | `vad_worker.py` |
| Gladia Live init | `Multilingual_.../gladia_service.py` L34–57 | `gladia_live_stt.py` |
| TTS pop-skip + batch | `v3/.../uplift_service.py` L133–153 | `uplift_tts.py` |
| Client prebuffer + flush | `v3/frontend/index.html` L212, L331–365, L461–466 | `examples/web-client/index.html` |
| LiveKit turn_handling | `habiba-sdk-agent/worker/main.py` L190–197 | `config.py` defaults |
| Interruption test (min words) | `habiba-sdk-agent/tests/test_interruption.py` | `test_barge_verify_live.py` |

---

## 12. Glossary of Voice Agent Terms

| Term | Definition |
|------|-----------|
| **VAD** | Voice Activity Detection — classifies audio frames as speech or silence |
| **Endpointing** | Deciding when the user has finished speaking (VAD silence or STT endpoint) |
| **Barge-in** | User interrupting the agent mid-utterance |
| **TTFT** | Time To First Token — LLM latency to first generated token |
| **TTFB** | Time To First Byte — TTS latency to first audio chunk |
| **TTFA** | Time To First Audio — end-to-end perceived latency (user stop → agent start) |
| **Hangover** | Keeping "speech" state for a few frames after energy drops (prevents choppy end) |
| **Hysteresis** | Requiring N consecutive frames before state transition (prevents flicker) |
| **Pre-roll / lookback** | Audio captured before VAD onset, prepended to STT payload |
| **Noise floor** | Baseline RMS energy of ambient room sound |
| **Jitter buffer** | Client-side audio queue that smooths network timing variance |
| **Ghost chunks** | In-flight audio bytes that arrive after barge-in cancel |
| **Three-point cancel** | Atomic cancellation of producer (LLM), sender (TTS), transport (queue) |
| **False interruption** | Brief noise mistaken for barge-in (cough, desk tap) |
| **Verify window** | Pause period (700 ms) to confirm barge-in before committing |
| **Sentence chunking** | Splitting LLM stream into speakable units for TTS |
| **Speculative RAG** | Prefetching retrieval on partial STT before final transcript |
| **Canonical frame** | 512 samples, 16 kHz, mono, PCM16 = 1024 bytes = 32 ms |
| **μ-law** | Telephony audio encoding (8 kHz); transcoded to 16 kHz PCM for pipeline |
| **FSM** | Finite State Machine governing session/turn lifecycle |
| **SLO** | Service Level Objective — latency targets (p50, p95) |
| **Waterfall** | Per-turn timestamp trace across pipeline stages |

---

## Appendix A — `process_frame_async` Target Implementation

```python
async def process_frame_async(self, frame: AudioFrame) -> VADEvent:
    agent_speaking = self.fsm.state == SessionState.AGENT_SPEAKING

    # 1. Listening engine: gate → VAD → events
    evt = await self._speech_capture.process(frame, agent_speaking=agent_speaking)

    # 2. Barge-in during agent playback
    if evt.speech_start and agent_speaking:
        if self._config.enable_barge_verify:
            await self._barge_verify.on_speech_start_during_playback(self)
        else:
            self._legacy_immediate_barge_in()
        return evt

    # 3. Begin speech capture (with pre-roll)
    if evt.speech_start and not self._capturing_speech:
        self._begin_speech_capture()  # prepends pre-roll, does NOT clear

    # 4. Accumulate + stream to STT
    if self._capturing_speech and frame.pcm16:
        self._append_speech(frame.pcm16)
        if self._config.enable_streaming_stt:
            await self._stt_live.publish_audio(frame.pcm16)

    # 5. Endpoint
    if evt.speech_end and self._capturing_speech:
        self._end_speech_capture()
        if not self._config.enable_streaming_stt:
            self._speech_end_pending = True

    return evt
```

---

## Appendix B — Phase 0 Quick Wins (Implement Today)

These three changes stop the demo "hello" loop without the full refactor:

```python
# 1. silero_adapter.py
self._min_speech_frames = 4   # was 2
self._min_silence_frames = 12  # was 3

# 2. gladia_stt.py (mock path)
if len(buf) < _MIN_PCM_BYTES:
    return  # yield nothing

# 3. pipeline.py (speech_start handler)
# DELETE: self._speech_buffer = bytearray()
# KEEP: self._capturing_speech = True

# 4. pipeline.py (__init__)
self.three_point_cancel.register_flush_callback(self._flush_egress_queue)
```

---

*Document version: 1.0 — 2026-08-29*  
*Author: UCVE Voice Pipeline Engineering*  
*Next action: Execute Phase 0 + Phase 1*
