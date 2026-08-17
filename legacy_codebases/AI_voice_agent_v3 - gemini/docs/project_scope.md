# Project Scope: Ultra-Low Latency Urdu AI Voice Agent

---

## 1. Overview
We are building a highly modular, real-time, bidirectional AI Voice Agent optimized for Urdu and mixed Urdu-English speech. The current implementation is a fully asynchronous streaming pipeline in Python designed to minimize turn latency while keeping the codebase easy to trace from socket input to synthesized audio output.

### Core Tech Stack
- **Backend Framework:** `Python` with `FastAPI` on ASGI.
- **STT (Speech-to-Text):** `Gladia` for live bilingual transcription.
- **LLM (Language Model):** `Gemini` for low-latency response generation.
- **TTS (Text-to-Speech):** `Uplift` for streaming audio synthesis.
- **Transport:** `FastAPI WebSocket` for full-duplex client streaming.

---

## 2. Global Directory Architecture
The project keeps a strict separation between transport, AI services, prompts, and tests so each stage of the pipeline can be reasoned about independently.

```text
AI_voice_agent/
├── backend/
│   └── app/
│   │   ├── core/
│   │   │   └── config/config.py
│   │   │   └── prompts/
│   │   │       └── retail_prompt.md
│   │   ├── services/
│   │   │   ├── __init__.py # (implicit)
│   │   │   ├── gladia_service.py
│   │   │   ├── gemini_service.py
│   │   │   └── uplift_service.py
│   │   ├── transport/
│   │   │   ├── __init__.py
│   │   │   ├── websocket.py
│   │   │   ├── connection_manager.py
│   │   │   ├── audio_receiver.py
│   │   │   └── audio_sender.py
│   │   └── main.py
├── backend/
│   └── tests/ # Integration tests for each service
├── docs/
│   ├── HANDOFF.md
│   └── ...
├── frontend/
│   └── index.html
├── .env # Root .env file for secrets
├── requirements.txt
└── README.md
```

---

## 3. Protocol Architecture
*   **Client-to-Backend:** A persistent `WebSocket` at `ws://.../ws/audio` carries raw audio bytes from the user into the backend and returns synthesized audio bytes and metrics back to the client.
*   **Backend-to-AI:** The backend maintains separate async integrations for `Gladia`, `Gemini`, and `Uplift`. Each service is wrapped in a dedicated class so the stages can stream independently and stay loosely coupled.
*   **Pipeline Shape:** The live flow is `WebSocket -> AudioReceiver -> GladiaService -> GeminiService -> UpliftTTSService -> AudioSender -> WebSocket`.

---

## 4. PHASE 0: Application Bootstrap
*   **Objective:** Load runtime secrets early, fail fast when a key is missing, and mount the WebSocket pipeline under a single FastAPI app.
*   **Location:** `backend/app/main.py`

### A. Component Index
*   `main.py`: Loads `.env`, validates `GEMINI_API_KEY`, `GLADIA_API_KEY`, and `UPLIFT_API_KEY`, configures CORS, and registers the transport router.
*   `lifespan(app)`: Emits startup and shutdown logs for the backend process.
*   `root_check()`: Simple health endpoint that confirms the backend is online.

### B. Core Principles
1.  **Fail Fast on Missing Secrets:** The app exits immediately if any provider key is absent or empty.
2.  **Single Entry Point:** The backend server stays centered on one ASGI app so the transport layer remains easy to trace.

---

## 5. PHASE 1: The Transport Layer
*   **Objective:** Ingest raw audio from the client, buffer it safely, and stream AI audio back without blocking the event loop.
*   **Location:** `backend/app/transport/`

### A. Component Index
*   `websocket.py`: Defines the `/ws/audio` route and the session orchestrator that connects STT, LLM, and TTS.
*   `connection_manager.py`: Maintains a thread-safe registry of active WebSocket connections keyed by `session_id`.
*   `audio_receiver.py`: An inbound `asyncio.Queue` wrapper that stores raw audio chunks from the client.
*   `audio_sender.py`: An outbound `asyncio.Queue` worker that pushes synthesized audio to the correct WebSocket.

### B. Class and Function Map
*   `ConnectionManager.__init__()`: Creates the active connection dictionary and async lock.
*   `ConnectionManager.connect()`: Accepts the WebSocket handshake and registers the connection.
*   `ConnectionManager.disconnect()`: Removes a session from the registry.
*   `ConnectionManager.get_connection()`: Returns the live WebSocket for a given session.
*   `AudioReceiver.__init__()`: Builds the inbound queue for a session.
*   `AudioReceiver.enqueue_chunk()`: Adds new raw audio bytes to the queue.
*   `AudioReceiver.get_next_chunk()`: Retrieves the next chunk for STT processing.
*   `AudioSender.__init__()`: Creates the outbound queue and running flag.
*   `AudioSender.queue_output_chunk()`: Enqueues AI audio for delivery.
*   `AudioSender.send_loop()`: Continuously drains the queue and sends bytes to the connected client.
*   `AudioSender.stop()`: Stops the outbound loop safely.
*   `audio_endpoint(websocket)`: Allocates the session objects, starts the sender loop, launches the orchestrator, and receives inbound audio bytes.

### C. Core Principles
1.  **No Blocking Operations:** The transport layer is built entirely on `async/await` so multiple users can stream concurrently.
2.  **Safe Cleanup:** The endpoint and sender loop both handle disconnects and cancellation so session state is released cleanly.

---

## 6. PHASE 2: The Speech-to-Text (STT) Pipeline
*   **Objective:** Take raw PCM audio from `AudioReceiver` and transcribe it in real time into structured text, including mixed Urdu-English speech.
*   **Technology:** `gladiaio-sdk` for Python.
*   **Core Component:** `backend/app/services/gladia_service.py`

This phase is implemented as a sequential and event-driven pipeline within `GladiaService`.

### A. Stage 1: Defining the Transcription Configuration
*   **Function:** `_build_live_init_request()`
*   **Purpose:** Builds the live session request sent to Gladia with the exact low-latency configuration used by the project.
*   **Key Parameters:**
    *   `model="solaria-1"`: Uses the streaming model configured in the code.
    *   `encoding="wav/pcm"`, `sample_rate=16000`, `bit_depth=16`, `channels=1`: Matches the audio format expected from the transport layer and test fixtures.
    *   `endpointing=0.5`: Triggers final results after a short silence window.
    *   `language_config`: Enables `ur` and `en` with code switching.
    *   `messages_config`: Subscribes only to partial transcripts, final transcripts, and errors to keep the event stream lean.

### B. Stage 2: Defining the Output Data Structure
*   **Class:** `GladiaTranscript` (dataclass)
*   **Purpose:** Normalizes every transcript into a predictable payload with `session_id`, `text`, `is_final`, `language`, and `raw_message`.

### C. Stage 3: Parsing Incoming Messages
*   **Function:** `_extract_text()`
*   **Purpose:** Safely extracts transcript text and metadata from the raw SDK message, handling dict-like and object-like payloads.

### D. Stage 4: Orchestrating the Real-time STT Session
*   **Class:** `GladiaService`
*   **Purpose:** Owns the live Gladia session for a single user and bridges audio ingestion to transcript callbacks.
*   **Lifecycle Methods:**
    *   `__init__(...)`: Sets up queues, callbacks, session state, and cancellation flags.
    *   `start()`: Creates the live Gladia session, binds events, and launches the concurrent sender and receiver loops.
    *   `stop_recording()`: Cancels the loops and closes the live session idempotently.
*   **Observer Hooks:**
    *   `on_transcript(callback)`: Registers normalized transcript consumers such as the Groq stage.
    *   `on_message(callback)`: Registers raw message consumers for debugging or telemetry.

### E. Stage 5: Session Creation and Event Binding
*   **Function:** `_create_session()`
*   **Purpose:** Instantiates the Gladia client, resolves the live async API surface, and opens the live session.
*   **Function:** `_bind_session_events(session)`
*   **Purpose:** Hooks Gladia message, error, and ended events into the local queue and lifecycle flags.

### F. Stage 6: Concurrent Worker Loops
*   **Function:** `_send_audio_loop()`
*   **Purpose:** Drains raw audio from `AudioReceiver` and streams it into Gladia.
*   **Function:** `_receive_loop()`
*   **Purpose:** Pulls normalized transcript payloads from the internal queue, converts them into `GladiaTranscript`, logs them, and dispatches them to listeners.

### G. Stage 7: Low-level Audio Publication
*   **Function:** `publish_audio(chunk)`
*   **Purpose:** Sends a single audio chunk directly to the active Gladia session.

### H. Operational Checks & QA
*   **Endpointing Tuning:** `endpointing=0.5` is the current balance point between responsiveness and interruption risk.
*   **Disconnect Cleanup:** `stop_recording()` is the critical cleanup path that prevents abandoned live sessions.
*   **Test Coverage:** `backend/tests/test_gladia_pipeline.py` simulates a live audio stream and verifies the transcription callback path.

---

## 7. PHASE 3: The LLM Pipeline
*   **Objective:** Turn final user transcripts into short, coherent responses that can be streamed sentence by sentence.
*   **Technology:** `Google GenAI SDK` (Gemini API) async chat completions.
*   **Core Component:** `backend/app/services/gemini_service.py`

### A. Component Index
*   `GeminiService.__init__()`: Loads the prompt, initializes the official Google GenAI client (`genai.Client`), and seeds the conversation history.
*   `GeminiService.on_sentence(callback)`: Registers downstream consumers (like TTS) for completed sentences.
*   `GeminiService._find_chunk_split(text)`: Detects sentence boundaries using Urdu/English punctuation, pauses, and conjunction splitters.
*   `GeminiService.generate_reply(user_text)`: Streams Gemini output using `client.aio.models.generate_content_stream`, buffers tokens into complete sentences, and prunes history.
*   `GeminiService._dispatch_sentence(sentence)`: Delivers each completed sentence to the registered callbacks.

### B. Pipeline Notes
1.  **Prompt Loading:** The system prompt is read from `backend/app/core/prompts/retail_prompt.md` so the model behavior stays externalized.
2.  **Sentence Streaming:** The service does not wait for the full answer before emitting output; it dispatches completed sentences as soon as punctuation/conjunction splits close them.
3.  **History Control:** Conversation state is trimmed to the configured turn window (`GEMINI_MAX_HISTORY`) to avoid unbounded context growth.
4.  **QA Hook:** `backend/tests/test_gemini_pipeline.py` exercises the sentence streaming path with several scripted scenarios from `gemini_test_scenarios.json`.

---

## 8. PHASE 4: The TTS Pipeline
*   **Objective:** Convert streamed LLM sentences into audio bytes fast enough for live playback, while allowing cancellation when the user barges in.
*   **Technology:** `aiohttp` streaming requests to Uplift.
*   **Core Component:** `backend/app/services/uplift_service.py`

### A. Component Index
*   `TTSTimeoutError`: Raised when synthesis exceeds the configured timeout envelope.
*   `TTSRateLimitError`: Raised when the provider returns a rate-limit response after retries are exhausted.
*   `TTSProviderError`: Raised for provider-side errors and non-retryable failures.
*   `UpliftTTSService.__init__()`: Creates the HTTP session, configures pooling, and initializes the cancel flag.
*   `UpliftTTSService.cancel()`: Signals the active synthesis stream to stop.
*   `UpliftTTSService._reset_cancel()`: Clears the cancel flag at the beginning of a new turn.
*   `UpliftTTSService.aclose()`: Closes the HTTP session during shutdown.
*   `UpliftTTSService._synthesize_sentence(text, request_id)`: Performs the retrying streaming request and yields audio chunks.
*   `UpliftTTSService.stream_audio(text_iterator)`: Consumes Groq sentences and yields raw audio bytes to the sender.

### B. Pipeline Notes
1.  **Streaming First:** Audio is yielded as soon as chunks arrive rather than waiting for a full response.
2.  **Retry Boundaries:** Rate limits and provider failures are retried only within the configured maximum retry budget.
3.  **Barge-in Support:** The cancel flag allows the pipeline to stop TTS immediately when the user starts speaking again.
4.  **QA Hook:** `backend/tests/test_uplift_pipeline.py` validates the sentence-to-audio streaming path and raw byte output.

---

## 9. PHASE 5: The Conversation Orchestrator
*   **Objective:** Connect STT, LLM, and TTS into one turn-based conversation loop and handle interruptions cleanly.
*   **Core Component:** `backend/app/transport/websocket.py`

### A. Component Index
*   `_SentenceBridge`: An async queue bridge between Groq sentence output and Uplift sentence input.
*   `SessionOrchestrator.__init__()`: Instantiates the three service objects and wires their callbacks together.
*   `SessionOrchestrator.run()`: Starts the STT side of the pipeline for the session.
*   `SessionOrchestrator.shutdown()`: Stops the STT service, cancels any active turn, and closes TTS resources.
*   `SessionOrchestrator._on_sentence(sentence)`: Receives completed LLM sentences, emits metrics, forwards text to the frontend, and hands sentences to TTS.
*   `SessionOrchestrator._on_transcript(transcript)`: Receives STT results, sends user transcript events, and starts a new turn when the transcript is final.
*   `SessionOrchestrator._barge_in()`: Cancels active AI speech and clears queued audio when the user interrupts.
*   `SessionOrchestrator._flush_audio_queue()`: Empties the sender queue so stale audio cannot play later.
*   `SessionOrchestrator._run_turn(user_text)`: Executes a full user turn from transcript to spoken response.

### B. Bridge Behavior
*   `_SentenceBridge.put(sentence)`: Accepts new LLM sentences as they are emitted.
*   `_SentenceBridge.close()`: Signals the end of the turn to the TTS consumer.
*   `_SentenceBridge.__aiter__()` and `_SentenceBridge._drain()`: Provide the async iterator interface that `UpliftTTSService.stream_audio()` consumes.

### C. Conversation Flow
1.  The user streams mic audio into `AudioReceiver`.
2.  `GladiaService` transcribes the audio and emits partial and final transcripts.
3.  The orchestrator forwards final text into `GeminiService.generate_reply()`.
4.  Gemini emits complete sentences into `_SentenceBridge`.
5.  `UpliftTTSService` converts each sentence into audio chunks.
6.  `AudioSender` writes the bytes back to the client over the same WebSocket.

### D. Telemetry and Barge-in
*   The orchestrator measures Gemini latency, TTS latency, and total response time and sends those metrics to the frontend as JSON messages.
*   When new speech arrives during playback, the current turn is interrupted, the TTS stream is canceled, and any queued audio is flushed.

---

## 10. Testing and Support Utilities
*   **`backend/tests/audio_converter.py`**: Converts mobile recordings into the strict 16kHz, 16-bit, mono WAV format required by the STT stage.
*   **`backend/tests/test_gladia_pipeline.py`**: Simulates microphone streaming into the Gladia service.
*   **`backend/tests/test_gemini_pipeline.py`**: Exercises the Gemini sentence streaming path and logs time to first sentence.
*   **`backend/tests/test_uplift_pipeline.py`**: Exercises the TTS byte stream and writes raw output for inspection.

### Operational Checks & QA
- **Audio Format Discipline:** The STT stage expects PCM-compatible input that matches the documented test format exactly.
- **Prompt Integrity:** The Gemini prompt in `backend/app/core/prompts/retail_prompt.md` should remain aligned with the intended retail assistant behavior.
*   **Human-in-the-Loop Testing:** Mixed Urdu-English prompts should be validated against real microphone audio before release.

---

## 11. Current Implementation Summary
The project is no longer just a transport skeleton. It now contains a full turn-based voice loop with a concrete session orchestrator, live STT, streaming LLM output, streaming TTS, barge-in handling, and test utilities that mirror each stage of the pipeline.
