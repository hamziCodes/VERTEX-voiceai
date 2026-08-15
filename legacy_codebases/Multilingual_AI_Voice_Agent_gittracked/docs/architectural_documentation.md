# Multilingual AI Voice Agent — Architectural Documentation
**Version 2.0 | Post Audit-01 + Audit-02 Hardening**

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Directory Structure](#2-directory-structure)
3. [Core Principles & Design Patterns](#3-core-principles--design-patterns)
4. [Pipeline Stages — Full Lifecycle](#4-pipeline-stages--full-lifecycle)
   - 4.1 [Stage 1 — Transport & WebSocket Gateway](#41-stage-1--transport--websocket-gateway)
   - 4.2 [Stage 2 — STT: Gladia Live Transcription](#42-stage-2--stt-gladia-live-transcription)
   - 4.3 [Stage 3 — Language Routing & LLM Inference](#43-stage-3--language-routing--llm-inference)
   - 4.4 [Stage 4 — TTS: Dynamic Voice Synthesis](#44-stage-4--tts-dynamic-voice-synthesis)
5. [Session Orchestrator — State Machine](#5-session-orchestrator--state-machine)
6. [Concurrency & Async Architecture](#6-concurrency--async-architecture)
7. [Language Configuration System](#7-language-configuration-system)
8. [TTS Strategy Pattern — Dynamic Routing](#8-tts-strategy-pattern--dynamic-routing)
9. [WebSocket Message Protocol](#9-websocket-message-protocol)
10. [Configuration & Environment Schema](#10-configuration--environment-schema)
11. [How to Add a New Language](#11-how-to-add-a-new-language)
12. [Sequence Diagrams](#12-sequence-diagrams)

---

## 1. System Overview

The Multilingual AI Voice Agent is a **real-time, full-duplex voice pipeline** supporting live code-switching between English, Urdu, Arabic, and Malay. It operates as a customer-facing phone agent for Vertex Computers — a computer retail/repair store.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser / Client                            │
│  Microphone → PCMWorklet (16kHz) ←──────── AudioContext ←── AI PCM │
│                    │                                         ↑      │
│                    ▼                                         │      │
│              WebSocket (Binary + JSON frames)                │      │
└─────────────────────┬───────────────────────────────────────┘      │
                       │                                              │
                       ▼                                              │
┌──────────────────────────────────────────────────────────────────┐  │
│                    FastAPI Backend  (Python / asyncio)           │  │
│                                                                  │  │
│  WebSocket Gateway ──► AudioReceiver ──► GladiaService (STT)    │  │
│                                               │                  │  │
│                                               ▼ Transcript       │  │
│                                       SessionOrchestrator        │  │
│                                               │                  │  │
│                          ┌────────────────────┤                  │  │
│                          ▼                    ▼                  │  │
│                    LanguageRouter         GroqService (LLM)      │  │
│                          │                    │ sentences         │  │
│                          ▼                    ▼                  │  │
│                     TTSManager ◄──── _SentenceBridge             │  │
│                          │                                       │  │
│                          ▼                                       │  │
│         ┌────────────────────────────────┐                       │  │
│         │  Uplift │ Google │ ElevenLabs    │                       │  │
│         └────────────────────────────────┘                       │  │
│                          │ raw PCM @ 22050 Hz                    │  │
│                          ▼                                       │  │
│                     AudioSender ──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Transport | **FastAPI** + **WebSockets** | Full-duplex binary + JSON channel |
| STT | **Gladia Live V2** (`solaria-1`) | Code-switching transcription with endpointing |
| LLM | **Groq** (`llama-3.1-8b-instant`) | Token-streaming inference, 150 token cap |
| TTS (Urdu) | **Uplift AI** | PCM_22050_16, native Urdu voice |
| TTS (Arabic, Malay, English) | **Google Cloud TTS** | WaveNet voices, BCP-47 routing, 22050 Hz |
| TTS (English fallback) | **ElevenLabs** | `eleven_multilingual_v2`, pcm_22050 |
| Config | **Pydantic Settings** | `.env` validated at startup |
| Language Config | **YAML + Markdown** | Per-language strategy profiles |

---

## 2. Directory Structure

```
Multilingual_AI_Voice_Agent/
│
├── backend/
│   └── app/
│       ├── main.py                         # FastAPI app entrypoint, CORS, lifespan
│       │
│       ├── core/
│       │   ├── config/
│       │   │   ├── config.py               # Pydantic Settings (lru_cache singleton)
│       │   │   ├── language_registry.py    # Singleton. Parses all YAMLs at startup.
│       │   │   └── languages/              # Per-language strategy YAMLs
│       │   │       ├── ar.yaml             # Arabic → Google TTS
│       │   │       ├── en.yaml             # English → Google TTS (or ElevenLabs)
│       │   │       ├── ms.yaml             # Malay → Google TTS
│       │   │       └── ur.yaml             # Urdu → Uplift TTS
│       │   │
│       │   ├── prompts/
│       │   │   ├── base_system_prompt.md   # Permanent agent identity & rules
│       │   │   └── language_directives/    # Per-language ephemeral LLM directives
│       │   │       ├── ar.md               # Arabic: tone, register, brevity rules
│       │   │       ├── en.md               # English: conciseness, no slang
│       │   │       ├── ms.md               # Malay: respect register, hardware terms
│       │   │       └── ur.md               # Urdu: Nastaliq register, hardware terms
│       │   │
│       │   └── interfaces.py               # Provider Protocol contracts (STT/LLM/TTS)
│       │
│       ├── orchestration/
│       │   └── language_router.py          # Debounce-based language switch guard
│       │
│       ├── services/
│       │   ├── stt/                        # ← STT provider subpackage
│       │   │   ├── __init__.py
│       │   │   └── gladia_service.py       # Gladia Live V2 SDK wrapper
│       │   │
│       │   ├── llm/
│       │   │   ├── __init__.py
│       │   │   ├── groq_service.py         # Groq streaming + history management
│       │   │   └── prompt_builder.py       # Builds ephemeral per-turn message array
│       │   │
│       │   └── tts/                        # ← All TTS providers consolidated
│       │       ├── __init__.py
│       │       ├── tts_manager.py          # Switchboard: routes by language code
│       │       ├── uplift_service.py       # Uplift AI (Urdu)
│       │       ├── google_service.py       # Google Cloud TTS (ar, ms, en)
│       │       ├── elevenlabs_service.py   # ElevenLabs (en, with Google fallback)
│       │
│       └── transport/
│           ├── __init__.py
│           ├── websocket.py                # Gateway + SessionOrchestrator state machine
│           ├── audio_receiver.py           # Inbound audio queue (FIFO, bounded)
│           ├── audio_sender.py             # Outbound audio loop (maxsize=200)
│           └── connection_manager.py       # Global WebSocket session registry
│
├── backend/tests/
│   ├── test_groq_pipeline.py               # LLM streaming test
│   ├── test_gladia_pipeline.py             # STT connection test
│   ├── test_uplift_pipeline.py             # Uplift TTS synthesis test
│   ├── test_arabic_tts.py                  # Google TTS Arabic validation
│   └── test_orchestrator_arabic.py         # Full pipeline Arabic integration test
│
├── frontend/
│   └── index.html                          # All-in-one evaluation UI
│       # Includes: PCMWorkletProcessor (16kHz mic capture),
│       #           WebSocket client (binary + JSON),
│       #           PCMPlayerProcessor (22050 Hz playback),
│       #           Live transcripts, metrics, logs panel
│
├── docs/
│   └── architectural_documentation.md      # This document
│
├── Antigravity/
│   ├── codebase_audit01                    # Audit 1 findings
│   ├── codebase_audit02                    # Audit 2 findings (Phase 1)
│   ├── Codebase01_FIXES                    # Audit 1 implemented fixes log
│   └── Codebase02_FIXES                    # Audit 2 implemented fixes log
│
├── .env                                    # Runtime secrets (never committed)
├── .env.example                            # Template for all required variables
├── requirements.txt                        # Python dependencies
└── README.md
```

---

## 3. Core Principles & Design Patterns

### 3.1 Strategy Pattern (TTS Routing)
Every language maps to a named `TTSProvider` strategy. `TTSManager` holds all providers warm and routes via a simple dictionary lookup — `O(1)` at turn time. Adding Arabic TTS means adding one YAML field, not touching the orchestrator.

### 3.2 Provider Protocol Contracts
`interfaces.py` defines three `Protocol` classes:
- **`STTProvider`**: `start()`, `stop()`, `on_transcript()`
- **`LLMProvider`**: `generate_reply(user_text, lang_profile)`, `on_sentence()`
- **`TTSProvider`**: `stream_audio(text_iter, language_code)`, `cancel()`, `aclose()`, `sample_rate_hz`

The orchestrator imports **only these protocols** — never concrete vendor classes.

### 3.3 Configuration-Driven Behaviour
Every per-language decision (TTS provider, voice ID, LLM directive, STT hint, sample rate) lives in a YAML file under `languages/`. The Python code is language-agnostic; it reads the profile and delegates.

### 3.4 Singleton Configuration
Both `Settings` (`get_settings()`) and `LanguageRegistry` are process-level singletons. YAML files and `.env` are read exactly once — at process startup — regardless of concurrent sessions.

### 3.5 Asyncio-First
All I/O (STT websocket, LLM streaming HTTP, TTS HTTP) is `async`. The entire server is single-threaded. The concurrency model relies on cooperative yielding at `await` points — no threads, no thread locks.

---

## 4. Pipeline Stages — Full Lifecycle

### 4.1 Stage 1 — Transport & WebSocket Gateway

**Files:** [`websocket.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/transport/websocket.py), [`audio_receiver.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/transport/audio_receiver.py), [`connection_manager.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/transport/connection_manager.py)

**What happens:**
1. Browser connects to `ws://localhost:8000/ws/audio`.
2. `ConnectionManager.connect()` accepts the WebSocket handshake and registers the session ID.
3. `AudioReceiver` is created — a bounded `asyncio.Queue(maxsize=100)` FIFO buffer.
4. `AudioSender` is created — a bounded `asyncio.Queue(maxsize=200)` FIFO buffer + background `send_loop()`.
5. `SessionOrchestrator` is created and wired. All pipeline components are instantiated.
6. The gateway loop runs `await websocket.receive_bytes()` in a tight loop, pushing each binary chunk into `AudioReceiver`.

**Key design points:**
- The gateway loop is intentionally **bare and thin** — it does nothing except receive and enqueue. All intelligence lives in the orchestrator.
- `AudioReceiver.enqueue_chunk()` uses `put_nowait()` with tail-drop (drops oldest when full) to prevent the buffer from blocking the gateway loop.
- `AudioSender.send_loop()` stops itself (`_is_running = False`) if `send_bytes()` fails — preventing zombie synthesis for disconnected clients.

**Inbound audio format:** Raw PCM, 16-bit signed, 16 kHz, mono (produced by `PCMWorkletProcessor` in the browser).

---

### 4.2 Stage 2 — STT: Gladia Live Transcription

**File:** [`gladia_service.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/services/stt/gladia_service.py)

**What happens:**
1. `GladiaService.start()` calls `_create_session()` to handshake with the Gladia Live V2 SDK.
2. The session is configured with `solaria-1` model, `wav/pcm` encoding at 16kHz, `endpointing=0.2` (200ms silence = end of utterance), and code-switching across `[ur, en, ar, ms]`.
3. `_bind_session_events()` registers three SDK event listeners:
   - `"message"` → extracts text, pushes normalized dict to `_transcript_queue` (maxsize=50).
   - `"error"` → logs error.
   - `"ended"` → clears `_running` flag, sets `_ended_evt`.
4. Two concurrent asyncio tasks are launched via `asyncio.gather()`:
   - **`_send_audio_loop`**: Continuously dequeues PCM from `AudioReceiver` and calls `session.send_audio()`.
   - **`_receive_loop`**: Dequeues from `_transcript_queue`, normalizes to core `Transcript` dataclass, dispatches to all registered `TranscriptCallback` listeners.

**Gladia Configuration Details:**

| Parameter | Value | Rationale |
|---|---|---|
| Model | `solaria-1` | Gladia's highest-accuracy multilingual model |
| Encoding | `wav/pcm` | Matches browser PCMWorklet output format |
| Sample Rate | 16000 Hz | Standard for voice transcription |
| Endpointing | 0.2s | 200ms silence triggers final transcript |
| Code-switching | `True` | Allows mid-sentence language change detection |
| Languages | `[ur, en, ar, ms]` | All supported languages declared upfront |
| Partial transcripts | `True` | Enables streaming interim results to UI |

**Stop/Teardown Flow:**
`stop_recording()` clears `_running`, calls `session.stop_recording()`, then waits on `_ended_evt` (with 1.0s timeout) for the SDK to signal network closure — replacing the original hardcoded `sleep(0.5)`.

---

### 4.3 Stage 3 — Language Routing & LLM Inference

**Files:** [`language_router.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/orchestration/language_router.py), [`groq_service.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/services/llm/groq_service.py), [`prompt_builder.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/services/llm/prompt_builder.py)

#### LanguageRouter — Debounce Guard

The router prevents chaotic TTS provider switching caused by single-word utterances or accidental language blips.

**Algorithm:**
```
input: detected_code (from Gladia), word_count (from transcript)

if no detected_code → return current
normalize: base_lang = detected_code.split('-')[0].lower()  # "en-US" → "en"
if unsupported → return current

if word_count < 3 (short utterance):
    if same as last_detected_lang: consecutive_count += 1
    else: reset, last = base_lang, count = 1
    if count >= 2: switch language, reset debounce
else (full sentence, 3+ words):
    switch immediately if different
    reset debounce
```

| Utterance | Words | Action |
|---|---|---|
| "Yes" | 1 | Debounced — no switch unless repeated |
| "Shukriya" | 1 | Debounced |
| "مجھے ایک لیپ ٹاپ چاہیے" | 5 | Immediate switch to Urdu |
| "أريد شراء جهاز كمبيوتر" | 4 | Immediate switch to Arabic |

#### Groq Service — Streaming LLM Inference

**Conversation memory:** Each `GroqService` instance maintains a `history` list scoped to one session. History contains only permanent base prompt + conversation turns. Language directives are **never stored** in history — they are ephemeral.

**Per-turn flow:**
1. `prompt_builder.build_messages()` constructs the final message array: `[base_prompt, ...history, ephemeral_language_directive, user_turn]`.
2. The ephemeral directive is injected immediately before the user's message — the closest position to the LLM's decision point.
3. Groq streams tokens via `chat.completions.create(stream=True, max_tokens=150)`.
4. The token stream is buffered. Every time `_is_sentence_end()` matches a sentence-ending punctuation (`. ? ! ۔ ؟`), the buffered sentence is dispatched.
5. Each dispatched sentence is pushed to all `_sentence_callbacks` as a fire-and-forget `asyncio.create_task()` with a done-callback for error logging.
6. After completion: the user turn + full AI reply are appended to history. History is pruned to `max_history_turns` (default 6 turns = 12 messages + base prompt).

**Prompt Architecture (per-turn message array):**

```
[
  { role: "system",    content: "<base_system_prompt.md>" },   # Agent identity + rules
  { role: "user",      content: "previous user turn 1" },      # Turn N-3
  { role: "assistant", content: "previous AI reply 1" },       # Turn N-3
  ...history...
  { role: "system",    content: "<language_directive>" },       # EPHEMERAL: e.g. ar.md
  { role: "user",      content: "current user utterance" }      # Current turn
]
```

---

### 4.4 Stage 4 — TTS: Dynamic Voice Synthesis

**Files:** [`tts_manager.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/services/tts/tts_manager.py), [`google_service.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/services/tts/google_service.py), [`uplift_service.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/services/tts/uplift_service.py), [`elevenlabs_service.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/services/tts/elevenlabs_service.py)

**The bridge between LLM and TTS is `_SentenceBridge`** — a bounded `asyncio.Queue(maxsize=50)` that acts as an async generator. It decouples sentence emission (LLM callback) from sentence consumption (TTS stream), allowing concurrent forward progress while maintaining backpressure.

**Per-sentence synthesis flow:**
1. `groq_service._dispatch_sentence()` calls `_on_sentence()` → `bridge.put(sentence)`.
2. The TTS provider's `stream_audio(bridge, language_code)` async generator dequeues sentences.
3. For each sentence, the provider calls its vendor API.
4. The response is chunked and accumulated in a `leftover` buffer. When `len(leftover) >= buffer_size`, aligned byte chunks are yielded.
5. `websocket.py` receives each `audio_chunk` and passes it to `AudioSender.queue_output_chunk()`.
6. `AudioSender.send_loop()` dequeues and calls `websocket.send_bytes()`.

**TTS Provider Routing Table:**

| Language | YAML Provider | Service Class | Voice | Format |
|---|---|---|---|---|
| Urdu (`ur`) | `uplift` | `UpliftTTSService` | `uplift_voice_id` from `.env` | PCM_22050_16 |
| Arabic (`ar`) | `google` | `GoogleTTSService` | `ar-XA-Wavenet-A` | LINEAR16 @ 22050Hz |
| Malay (`ms`) | `google` | `GoogleTTSService` | `ms-MY-Wavenet-A` | LINEAR16 @ 22050Hz |
| English (`en`) | `google` | `GoogleTTSService` | `en-US-Wavenet-A` | LINEAR16 @ 22050Hz |
| English (primary) | `elevenlabs` | `ElevenLabsTTSService` | `pNInz6obpgDQGcFmaJgB` | pcm_22050 |

**Sample Rate Contract:**
All providers expose `sample_rate_hz: int = 22050`. The orchestrator asserts this before the first chunk is synthesized:
```python
assert tts_provider.sample_rate_hz == 22050, f"Unsupported sample rate: {tts_provider.sample_rate_hz}"
```

**Uplift-specific: Pop-Sound Trim**
The first 2048 bytes of each Uplift synthesis session are silently discarded (`bytes_to_skip = 2048`) to eliminate an audio artifact in the Uplift API response header. This only applies to the first sentence per turn.

**Google TTS-specific:**
- BCP-47 language code mapping: `ar → ar-XA`, `ms → ms-MY`, `en → en-US`, `ur → ur-PK`.
- Voice ID override: If `LanguageProfile.tts_voice_id` is set in YAML, it overrides the default voice map.
- Chunking: Google returns the entire sentence as a single base64-encoded JSON blob. It is decoded and re-chunked into 4096-byte segments to satisfy the client prebuffering threshold.

---

## 5. Session Orchestrator — State Machine

**File:** [`websocket.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/transport/websocket.py)

`SessionOrchestrator` owns the turn lifecycle for one WebSocket session.

### State Transitions

```
           ┌─────────────────────────────────────────────────────┐
           │                      LISTENING                       │
           │   Waiting for a final transcript from Gladia         │
           └───────────────────┬──────────────────────────────────┘
                               │ Final transcript + is_final=True
                               ▼
           ┌─────────────────────────────────────────────────────┐
           │                      THINKING                        │
           │   Groq streaming tokens → dispatching sentences      │
           └───────────────────┬──────────────────────────────────┘
                               │ First audio chunk received
                               ▼
           ┌─────────────────────────────────────────────────────┐
           │                      SPEAKING                        │
           │   AudioSender draining synthesized chunks            │
           └───────────────────┬──────────────────────────────────┘
                               │ _run_turn() completes or barge-in
                               ▼
                          LISTENING
```

### Barge-In Flow

Barge-in is triggered when a transcript arrives (partial OR final) while state is `THINKING` or `SPEAKING`, and the utterance has more than 1 word or 2 characters.

```
Transcript arrives → _on_transcript() [inside _turn_lock]
  → state is THINKING or SPEAKING
  → _barge_in():
      1. TTSManager.cancel_active()   # Sets cancel_evt on active TTS
      2. Cancel & await _llm_task     # Cancels Groq stream
      3. Cancel & await _turn_task    # Waits for _run_turn to fully exit
      4. AudioSender.flush()          # Drains queued audio chunks
      5. send_text({"type":"control","action":"barge_in"})  # Frontend clears buffer
      6. state = LISTENING
```

### Turn Lock

`self._turn_lock = asyncio.Lock()` serializes all code inside `_on_transcript()`. This is the primary guard against the orphaned-task race where two rapid final transcripts could both pass the state guard during the asynchronous yield gap of `_barge_in()`.

---

## 6. Concurrency & Async Architecture

### Task Map (per session)

```
audio_endpoint()
├── sender_task = asyncio.create_task(audio_sender.send_loop())
│         Drains AudioSender queue → send_bytes() to client
│
└── pipeline_task = asyncio.create_task(orchestrator.run())
          └── gladia.start()
                    ├── audio_task = asyncio.create_task(_send_audio_loop())
                    │         AudioReceiver → gladia.send_audio()
                    └── receive_task = asyncio.create_task(_receive_loop())
                              → dispatches callback tasks:
                                    callback_task = asyncio.create_task(_on_transcript())
                                              └── [if final + LISTENING]
                                                    _turn_task = asyncio.create_task(_run_turn())
                                                              ├── _llm_task = asyncio.create_task(_llm_job())
                                                              │         GroqService.generate_reply()
                                                              │                 └── sentence_task = create_task(callback(sentence))
                                                              └── async for audio_chunk in tts.stream_audio(bridge):
                                                                        audio_sender.queue_output_chunk(chunk)
```

### Key Concurrency Rules

| Concern | Mechanism |
|---|---|
| Turn serialization | `_turn_lock` (asyncio.Lock) guards `_on_transcript()` |
| Barge-in TTS cancel | `cancel_evt.set()` in TTS provider, checked per-chunk |
| Orphan task prevention | `_turn_task` cancelled AND awaited before state reset |
| LLM leak prevention | `_llm_task` cancelled in both `_barge_in()` and `shutdown()` |
| Send failure detection | `AudioSender` stops loop on `send_bytes()` exception |
| Queue overflow | `_transcript_queue(maxsize=50)` drops with warning; `_SentenceBridge(maxsize=50)` blocks via `await put()` |

---

## 7. Language Configuration System

### YAML Profile Schema

Each file in `backend/app/core/config/languages/` follows this schema:

```yaml
code: ar                          # ISO 639-1 code (used as routing key)
name: Arabic                      # Human-readable name for logs
script: arabic                    # Script type: "arabic" | "latin" | "devanagari"
tts_provider: google              # Provider key in TTSManager._providers dict
tts_voice_id: null                # Override voice. null = use GOOGLE_VOICES default
llm_directive_file: language_directives/ar.md   # Relative to prompts/ directory
stt_hint: ar                      # Hint passed to Gladia (future use)
tts_sample_rate: 22050            # Must always be 22050 — enforced by assertion
```

### LLM Directive Architecture

The directive system implements **ephemeral per-turn language injection**. Directives are:
- Loaded from `.md` files at startup (once, by `LanguageRegistry`).
- Stored in `LanguageProfile.llm_directive_text` (immutable, in-memory).
- Injected at position `[-2]` in the message array (just before the user's message).
- **Never stored in `history`** — they do not pollute the conversation context.

**Directive content includes:**
- Language & script to respond in
- Register and tone instructions (formal/informal)
- Technical term handling (e.g., keep CPU, RAM, SSD in English)
- Brevity constraints (1-2 sentences)
- Script-specific punctuation rules

### LanguageRegistry Singleton

```python
class LanguageRegistry:
    _instance = None

    def __new__(cls, ...):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._load_all_languages()
        self._initialized = True
```

Every call to `LanguageRegistry()` returns the **same object**. YAML parsing happens exactly once.

---

## 8. TTS Strategy Pattern — Dynamic Routing

### TTSManager as Switchboard

```python
class TTSManager:
    def __init__(self, registry):
        google_service = GoogleTTSService()
        self._providers = {
            "uplift":      UpliftTTSService(),
            "elevenlabs":  ElevenLabsTTSService(fallback_provider=google_service),
            "google":      google_service,
        }
```

All providers are **warm** (HTTP sessions open, connection pools alive). Language switching has zero initialization overhead.

### Turn-Time Routing Logic

```
_run_turn(user_text, lang_profile):
    tts_provider = await tts_manager.get_provider(lang_profile.code)
    #   → reads lang_profile.tts_provider (from YAML)
    #   → looks up self._providers[provider_name]
    #   → if unknown → warns + falls back to "google"
    
    assert tts_provider.sample_rate_hz == 22050
    
    async for audio_chunk in tts_provider.stream_audio(bridge, lang_profile.code):
        audio_sender.queue_output_chunk(audio_chunk)
```

### ElevenLabs Fallback Chain

```
ElevenLabsTTSService.stream_audio()
    → calls ElevenLabs API
    → if HTTP status != 200:
        → yield from self._fallback_provider.stream_audio()   # GoogleTTSService
    → if cancel_evt.is_set(): return
```

The fallback uses the **same `GoogleTTSService` instance** already held in `TTSManager._providers["google"]` — no new connection is created.

---

## 9. WebSocket Message Protocol

All JSON messages flow over the same WebSocket connection as binary audio frames.

### Client → Server (Binary)

Raw PCM audio frames: `bytes` — 16-bit signed, 16kHz, mono.

### Server → Client (Text JSON)

**Transcript Update:**
```json
{
  "type": "transcript",
  "speaker": "user",      // "user" | "ai"
  "text": "Hello...",
  "is_final": false       // Only present for "user" speaker
}
```

**Latency Metric:**
```json
{
  "type": "metric",
  "name": "Gladia STT Latency",   // or "Groq LLM Latency" | "TTS Latency" | "Total Response Time"
  "value": "342 ms",
  "highlight": true               // Optional, for Total Response Time
}
```

**Control Message:**
```json
{
  "type": "control",
  "action": "barge_in"            // Signal client to discard its audio playback buffer
}
```

### Latency Measurement Points

```
User stops speaking (final transcript)
          │
          ├─► [Gladia STT Latency] = time from STT start → final transcript
          │
          ├─► [Groq LLM Latency]  = time from final transcript → first sentence dispatched
          │
          ├─► [TTS Latency]       = time from first sentence → first audio chunk sent to client
          │
          └─► [Total Response Time] = sum of above (final transcript → first audio chunk)
```

### Client → Server (Text JSON — Future Extension)

The `audio_endpoint` gateway currently only handles binary frames via `receive_bytes()`. Text frame handling (e.g., mute/unmute control) would require switching to `receive()` + dispatch on `data["type"]` — flagged as a future enhancement in the audit.

---

## 10. Configuration & Environment Schema

**File:** [`config.py`](file:///d:/PROJECTS/PASSION%20PROJECTS/Multilingual_AI_Voice_Agent/backend/app/core/config/config.py)

All settings are validated by Pydantic at startup. Missing required fields cause `sys.exit(1)` via `main.py`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `GLADIA_API_KEY` | ✅ | — | Gladia Live V2 API key |
| `GROQ_API_KEY` | ✅ | — | Groq inference API key |
| `GROQ_MODEL` | ❌ | `llama-3.1-8b-instant` | Groq model ID |
| `GROQ_MAX_HISTORY` | ❌ | `6` | Number of past turns kept in memory |
| `UPLIFT_API_KEY` | ✅ | — | Uplift TTS API key |
| `UPLIFT_VOICE_ID` | ✅ | — | Uplift voice identifier |
| `GOOGLE_TTS_API_KEY` | ✅ | — | Google Cloud TTS API key |
| `ELEVENLABS_API_KEY` | ❌ | `""` | ElevenLabs API key (leave blank if not used) |
| `LOG_LEVEL` | ❌ | `INFO` | Logging verbosity (`DEBUG`/`INFO`/`WARNING`) |
| `CORS_ORIGINS` | ✅ | — | Required. Comma-separated origins (e.g., `http://localhost:8000`) |

**Server startup:** `python -m uvicorn backend.app.main:app --reload` or `python backend/app/main.py`.

---

## 11. How to Add a New Language

Adding a new language (e.g., French `fr`) requires **zero changes to Python code**.

**Step 1 — Create the YAML profile:**
```yaml
# backend/app/core/config/languages/fr.yaml
code: fr
name: French
script: latin
tts_provider: google
tts_voice_id: fr-FR-Wavenet-A
llm_directive_file: language_directives/fr.md
stt_hint: fr
tts_sample_rate: 22050
```

**Step 2 — Add the Google voice mapping (if needed):**
In `google_service.py`, add to the `GOOGLE_VOICES` and `GOOGLE_LANGUAGE_CODES` dictionaries:
```python
"fr": "fr-FR-Wavenet-A"      # in GOOGLE_VOICES
"fr": "fr-FR"                 # in GOOGLE_LANGUAGE_CODES
```

**Step 3 — Write the LLM directive:**
```markdown
# backend/app/core/prompts/language_directives/fr.md
Réponds exclusivement en français. Sois concis (1-2 phrases maximum).
Garde les termes techniques matériels (RAM, CPU, SSD, GPU) en anglais.
Utilise un registre professionnel et respectueux.
```

**Step 4 — Register with Gladia:**
In `gladia_service.py`, add `"fr"` to the `languages` list in `_build_live_init_request()`:
```python
languages=["ur", "en", "ar", "ms", "fr"],
```

**That's it.** On next server restart, `LanguageRegistry` auto-discovers `fr.yaml`, Gladia is told to detect French, `LanguageRouter` accepts `fr` as a valid code, and `TTSManager` routes to `google` with the French voice.

---

## 12. Sequence Diagrams

### Full Turn Lifecycle (Happy Path)

```
Browser          GladiaService        LanguageRouter     GroqService         TTSManager          AudioSender
   │                   │                    │                 │                   │                   │
   │──PCM bytes──►│    │                    │                 │                   │                   │
   │              │    │◄──send_audio()──   │                 │                   │                   │
   │              │    │──►(Gladia STT)     │                 │                   │                   │
   │              │    │◄──transcript ev.   │                 │                   │                   │
   │              │    │                    │                 │                   │                   │
   │◄──user txt───│    │                    │                 │                   │                   │  (partial)
   │              │    │──[is_final=True]──►│                 │                   │                   │
   │              │    │                    │──lang_profile──►│                   │                   │
   │◄──STT metric─│    │                    │                 │                   │                   │
   │              │    │                    │                 │──generate_reply()──│                   │
   │              │    │                    │                 │                   │                   │
   │              │    │                    │                 │──[sentence 1]─────►│──stream_audio()   │
   │◄──AI txt─────│    │                    │                 │                   │                   │
   │◄──LLM metric─│    │                    │                 │──[sentence 2]─────►│(appended to iter) │
   │              │    │                    │                 │                   │                   │
   │              │    │                    │                 │                   │──PCM chunk 1──────►│
   │◄──TTS metric─│    │                    │                 │                   │                   │
   │◄──audio bytes│    │                    │                 │                   │──PCM chunk 2──────►│
   │◄──audio bytes│    │                    │                 │                   │     ...            │
   │◄──total metr.│    │                    │                 │                   │                   │
   │              │    │                    │                 │──bridge.close()───►│                   │
   │              │    │                    │                 │                   │──flush leftover───►│
```

### Barge-In Flow

```
Browser      GladiaService     SessionOrchestrator    GroqService    TTSManager    AudioSender
   │               │                   │                   │              │              │
   │──PCM──────────►│                  │                   │              │              │
   │──PCM──────────►│ (user speaks)    │                   │              │              │
   │               │──partial transcr►│                   │              │              │
   │               │                  │──[THINKING/SPEAKING state]       │              │
   │               │                  │──cancel_active()──────────────────►              │
   │               │                  │──cancel+await _llm_task──────────►              │
   │               │                  │──cancel+await _turn_task          │              │
   │               │                  │──flush()──────────────────────────────────────►  │
   │◄──barge_in────│──────────────────│                   │              │              │
   │  (discards    │                  │──state=LISTENING  │              │              │
   │   playback)   │                  │                   │              │              │
   │               │──[new final tr]──►                   │              │              │
   │               │                  │──new _run_turn()──►              │              │
```
