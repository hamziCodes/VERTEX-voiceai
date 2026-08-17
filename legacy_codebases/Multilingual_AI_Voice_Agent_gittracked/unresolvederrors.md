# Unresolved Errors & Diagnostic Context Log (`unresolvederrors.md`)

This document aggregates all diagnostic context, root causes, stack traces, and applied fixes for the **Multilingual AI Voice Agent (`VERTEX/studio`)** project.

---

## 1. Problem Statement & Symptoms

- **Symptom 1**: The client connects to `ws://localhost:8000/ws/audio`, and the UI displays the initial greeting text (*"Hello! I am Zara from Vertex Computers..."*), but the agent does **not play voice audio** through the browser speakers.
- **Symptom 2**: The agent does **not process incoming user voice input**.
- **Symptom 3**: Backend console logs print repeated warnings:
  ```text
  WARNING: [VAD] Queue full - dropping chunk to prevent memory bloat.
  WARNING: [b631e896-cb90-441a-af91-00196f227a1b] Receiver queue full — dropped oldest chunk.
  ```

---

## 2. Root Cause Analysis

### A. STT Provider Failures (Gladia V2 API)
When the WebSocket connection is initialized, `SessionOrchestrator` starts `GladiaService` to connect to `https://api.gladia.io/v2/live`. This connection failed due to two issues:

1. **402 Payment Required (Quota Limit Reached)**:
   ```text
   gladiaio_sdk.network.http_client.HttpError: You used all your 10h of free audio transcription. Please visit app.gladia.io to upgrade your plan ! | G-6ce78c8d | 402 | POST /v2/live
   ```
2. **Network Timeout (`httpcore.ConnectTimeout` / `10s TimeoutError`)**:
   ```text
   gladiaio_sdk.network.http_client.TimeoutError: Request timed out after 10s on attempt 1 (duration=22.312s) for POST https://api.gladia.io/v2/live
   ```

### B. Cascading WebSocket & ASGI Disconnect Loop
1. When Gladia STT initialization failed, Gladia's SDK threw an unhandled background exception or closed its socket.
2. `orchestrator.run()` failed, marking `pipeline_task` as completed with an error.
3. When `session.py` or `websocket.py` attempted to send an error JSON payload to the client via `websocket.send_text()`, Starlette/Uvicorn threw:
   ```text
   websockets.exceptions.InvalidState: connection is closing
   starlette.websockets.WebSocketDisconnect
   uvicorn.protocols.utils.ClientDisconnected
   ```
4. The exception escaped out of `audio_endpoint`, triggering Uvicorn's `finally:` cleanup block:
   - `greeting_task.cancel()` was called, **cancelling the TTS audio playback worker** before the 54 audio chunks (217,622 bytes) could reach the browser speakers.
   - The browser WebSocket was closed immediately with code `1006`.

---

## 3. Fixes & Refactorings Applied

### A. Branding & UI Design Language (`DESIGN.md` - VERTEX/studio)
- **`frontend/styles.css`**: Updated to Void Black (`#000000`) theme, Google Fonts (`DM Sans`, `Inter`, `JetBrains Mono`), rectangular spec geometry (removed all pill/capsule shapes).
- **`frontend/index.html`**: Updated brand lockup mark to `VERTEX/studio`, tagline *"We Build Digital Realities."*, logo mark (`nobg_logo_1.png`), and System Info Modal:
  - **Engineer**: `VERTEX/studio`
  - **Contact**: `vertex11solution@gmail.com`
- **`frontend/visualizer.js`**: Updated 3D particle wave colors to VERTEX Void accents (`#00c6ff` Cyan, `#0070f3` Electric Blue, `#7928ca` Violet Depth).

### B. Error Handling & Stability Improvements
- **`frontend/app.js`**: Added explicit handler for `payload.type === "error"` to display system error messages directly in the UI transcript and system console logs.
- **`backend/app/services/stt/gladia_service.py`**: Added `try...except` in `start()` to capture `_create_session()` errors onto `self.last_error` and return gracefully rather than raising unhandled exceptions.
- **`backend/app/orchestration/session.py`**: Wrapped `_ws.send_text()` calls in `try...except` to prevent `WebSocketDisconnect` from throwing when emitting error payloads on closing sockets.
- **`backend/app/transport/websocket.py`**: Wrapped task cancellations and socket cleanup in `finally:` with `with contextlib.suppress(Exception):` to prevent cleanup errors from bubbling up as ASGI application crashes.

---

## 4. Next Steps for Future Resolution

When reopening this project:

1. **Update STT API Credentials**:
   - Obtain a fresh **Gladia V2 API Key** with available quota or replace `GLADIA_API_KEY` in `.env`.
   - Alternatively, swap Gladia for an alternative STT engine (Deepgram, AssemblyAI, or Whisper).
2. **Decouple Greeting Audio Stream**:
   - Refactor `trigger_greeting()` so that greeting audio synthesis and playout run completely independent of STT session initialization.
3. **Verify Network Connectivity**:
   - Ensure outbound HTTPS/WSS requests to `https://api.gladia.io/v2/live` are not blocked by firewall, VPN, or DNS timeouts.
