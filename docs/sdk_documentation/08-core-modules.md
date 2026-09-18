# Core Modules

The `core/` package is the shared internal library used by all Wavia services. It contains all domain logic, provider abstractions, and infrastructure primitives.

---

## Module Map

```
core/
├── buffers/         # Typed async queues, cancellation tokens, buffer policies
├── compliance/      # PII redaction, audit writing, tenant compliance profiles
├── db/              # PostgreSQL repositories (tenant, session, knowledge base)
├── errors/          # Error codes, UUID parsing utilities
├── fsm/             # Session state machine, states, events, barge-in controller
├── language/        # Text normalizer, sentence chunker, language router, registry
├── latency/         # Latency waterfall collector, playback metric handler
├── listening/       # VAD config, SpeechCaptureEngine, BargeVerifyEngine, FrameSlicer
├── mcp/             # Tool orchestrator, conversational filler synth
├── metering/        # Usage metering (STT seconds, TTS chars, LLM tokens)
├── observability/   # Structured logging (structlog-based)
├── providers/       # Provider factory, registry, failover, adapters, interfaces
├── rag/             # PgVectorRetriever, SpeculativeRetrieval
├── redis/           # Redis session store adapter
├── runtime/         # Environment helpers (is_test_env, require_production_secrets)
├── secrets/         # Per-tenant secret manager (provider API keys)
├── session/         # Redis-backed session store
├── storage/         # (future) Object storage primitives
├── transport/       # NativeWebSocketTransport, EgressResampler, Resampler
├── types/           # AudioFrame, ControlEventType, Resampler types
└── vad/             # SileroVADAdapter (ONNX-based VAD)
```

---

## `core/fsm` — Session State Machine

### `SessionFSM` (`session_fsm.py`)
Authoritative state machine governing a single voice session.

**Key methods:**
- `can_transition(event)` → `bool` — safe check before triggering
- `trigger(event)` → `SessionState` — advance state; raises `InvalidStateTransitionError` on illegal transition
- `state` → `SessionState` — current state property

**Transition table:** See `TRANSITION_TABLE` dict — a compile-time mapping of `(state, event) → next_state`.

### `BargeInController` (`barge_in.py`)
Manages barge-in detection state and commit/false-alarm logic.

### `ThreePointCancel` (`cancel_contract.py`)
Coordinates three-point cancellation: LLM task cancel → TTS task cancel → egress queue flush.

---

## `core/buffers` — Typed Queues

### `TypedAsyncQueue[T]`
A typed `asyncio.Queue` with named `BufferPolicy`:
- `maxsize` — queue capacity
- `overflow` — `BLOCK`, `DROP_OLDEST`, `DROP_NEWEST`

**Named policies:**
| Policy | Usage |
|---|---|
| `INBOUND_MIC_POLICY` | Audio ingress from client |
| `OUTBOUND_TTS_POLICY` | Agent PCM egress queue |

### `AsyncioCancellationToken`
Lightweight cancellation token for cooperative async task cancellation.

```python
token = AsyncioCancellationToken()
token.cancel()
if token.is_cancelled:
    break
```

---

## `core/listening` — Audio Ingress Pipeline

### `SpeechCaptureEngine`
V2 listening pipeline. Combines VAD, RMS gate, and lookback buffer.

**Method:**
- `observe(frame, agent_speaking)` → VAD event
- `begin_capture()` / `reset()` / `take_utterance()` → `bytes`

### `BargeVerifyEngine`
50–250ms window that verifies detected speech is genuine before committing a barge-in.

**Method:**
- `run(pause, resume, commit, is_speaking)` — async coroutine; calls one of the three callbacks
- `note_vad(probability)` — feed VAD probability
- `note_partial(text)` — feed STT partial text

### `FrameSlicer`
Slices large PCM chunks into canonical 10ms frames before VAD processing.

### `VADWorker`
Optional thread-pool executor for VAD to avoid blocking the event loop.

---

## `core/vad` — Voice Activity Detection

### `SileroVADAdapter`
Wraps the Silero VAD ONNX model for real-time frame-level speech detection.

- **Input:** `AudioFrame` (16 kHz, mono PCM16)
- **Output:** VAD event with `speech_start`, `speech_end`, `probability`

```python
adapter = SileroVADAdapter()
adapter.configure(
    min_speech_frames=3,
    min_silence_frames=8,
    threshold=0.5
)
evt = adapter.process_frame(frame)
```

---

## `core/providers` — Provider Abstraction

### `ProviderRegistry`
Global registry mapping string IDs → provider classes.

```python
ProviderRegistry.register_provider_class("gladia", GladiaSTTProvider)
ProviderRegistry.get_provider_class("gladia")  # → GladiaSTTProvider
```

### `FailoverRouter`
Priority-ordered failover wrapper for TTS synthesis. Retries with secondary if primary fails.

### Factory Functions
`core/providers/factory.py`:
- `build_stt_provider(provider_id, ...)` → `BaseSTTProvider`
- `build_llm_provider(provider_id, model=...)` → `BaseLLMProvider`
- `build_tts_provider(provider_id, ...)` → `BaseTTSProvider`
- `normalize_stt_provider(name)` / `normalize_llm_provider(name)` / `normalize_tts_provider(name)` — normalize aliases

---

## `core/language` — Text Processing

### `TextNormalizer`
Normalizes LLM output for TTS: removes markdown, expands abbreviations, handles numbers.

### `SentenceChunker`
Splits LLM token stream into sentence-level chunks for per-sentence TTS synthesis (reduces TTFB).

### `LanguageRouter`
Routes text through language-specific processing based on detected language code.

### `LanguageRegistry`
Loads per-language VAD profile defaults (e.g. longer silence timeout for Mandarin).

---

## `core/rag` — Retrieval-Augmented Generation

### `PgVectorRetriever`
Retrieves relevant context chunks from a pgvector-indexed PostgreSQL table for the current tenant.

**Usage:**
```python
retriever = PgVectorRetriever()
chunks = await retriever.retrieve(query_text, tenant_id, top_k=5)
```

### `SpeculativeRetrieval`
Triggers `PgVectorRetriever` on STT partial transcripts (during barge verify window) to pre-warm context before STT final.

---

## `core/compliance` — Data Governance

### `RedactionService`
PII redaction for transcript data. Activated when `compliance_tier` is `hipaa` or `gdpr_strict`.

```python
redacted = redaction_service.redact_transcript(
    [{"speaker": "user", "text": "My SSN is 123-45-6789"}],
    RedactionPolicy(redact_pii_in_transcript=True)
)
```

### `AuditWriter`
Writes structured audit events to the PostgreSQL audit log table.

### `TenantComplianceProfileLoader`
Loads per-tenant compliance configuration (tier, HIPAA BAA acknowledgement, etc.).

---

## `core/transport` — Network Primitives

### `NativeWebSocketTransport`
Wrapper around the Starlette WebSocket for typed send/receive:

- `send_audio_frame(pcm_bytes)` — send binary audio frame
- `send_control_event(event_type, payload)` — send JSON control event
- `close(websocket)` — close with clean handshake

### `EgressResampler`
Converts TTS provider-native sample rates to the 16 kHz output format:
```python
pcm_16k = EgressResampler.resample_to_16k(pcm_native, native_rate)
```

### `Resampler`
Client-side inbound resampler — converts client mic audio from arbitrary rates to 16 kHz.

---

## `core/latency` — Observability

### `LatencyCollector`
Aggregates per-turn latency samples.

### `LatencyWaterfall`
Per-turn timing structure:
- `vad_end_of_speech_ms`
- `stt_final_ms`
- `llm_ttft_ms`
- `tts_ttfb_ms`
- `playback_start_ms`
- `compute_e2e_latency()` → float (ms)

### `PlaybackMetricHandler`
Processes `playback_started` events from the client to compute client-side E2E latency.

---

## `core/mcp` — Model Context Protocol

### `ToolOrchestrator`
Executes LLM tool calls using registered MCP-compatible tool definitions.

### `ConversationalFillerSynth`
Synthesizes filler phrases ("Let me check on that...") while tool execution is in flight, reducing perceived latency.
