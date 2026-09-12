# UCVE Realtime Audio & Event WebSocket Protocol

## 1. Transport & Connection
- **Endpoint**: `ws://<host>:8081/ws/audio?token=<JWT>&stt_provider=...&llm_provider=...&tts_provider=...`
- **Authentication**: Ephemeral mint token issued via `POST /v1/session/mint`.
- **Multiplexing**: Single sovereign WebSocket carries both binary raw audio and JSON control frames.

---

## 2. Audio Framing Contract
- **Encoding**: Raw linear signed 16-bit PCM (`pcm_s16le`).
- **Sample Rate**: 16,000 Hz (16 kHz).
- **Channels**: 1 (mono).
- **Frame Size**: 320 bytes (10 ms) or 640 bytes (20 ms).
- **Format**: Sent as binary WebSocket frames (`opcode=0x02`).

---

## 3. Realtime Control & Telemetry Events (`UCVERealtimeEvent`)

Sent as JSON text WebSocket frames (`opcode=0x01`):

| Event Direction | Event Type | Payload Fields | Purpose & Meaning |
|---|---|---|---|
| **Client → Server** | `control.pong` | `{"t": timestamp_ms}` | Heartbeat response to server ping (prevents disconnect). |
| **Client → Server** | `control.playback_started` | `{"t": timestamp_ms, "kind": "playback_started"}` | **Phase 24 Latency Anchor**: Signals speaker heard first audio chunk. |
| **Client → Server** | `control.barge_in` | `{"rms": float, "t": timestamp_ms}` | Instant client-side mic energy cut-through signal. |
| **Client → Server** | `text.turn` | `{"text": string}` | Text input turn injection bypassing mic STT. |
| **Server → Client** | `control.ping` | `{"t": timestamp_ms}` | Liveness heartbeat (expected pong within 10s). |
| **Server → Client** | `transcript` | `{"speaker": "user"\|"agent", "text": string}` | Diarized live speech recognition and agent reply tokens. |
| **Server → Client** | `metric` | `{"event": string, "waterfall": {...}}` | Waterfall breakdown (`stt_final_ms`, `llm_ttft_ms`, `tts_ttfb_ms`, `e2e_latency_ms`). |
| **Server → Client** | `event` | `{"event_type": "session_ready"\|"audio_start"\|"audio_stop"\|"info"\|"error"}` | Session lifecycle state transitions. |
