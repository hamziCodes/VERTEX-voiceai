# WebSocket Protocol

Wavia uses a **binary + JSON multiplexed WebSocket protocol** on the `/ws/audio` endpoint. The client interleaves raw PCM audio (binary frames) with JSON control messages (text frames).

---

## Connection URL

```
ws://127.0.0.1:8081/ws/audio?token=<JWT>[&options]
```

### Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `token` | string | ✅ | — | Session JWT from `/mint` or `/v1/session` |
| `stt_provider` | string | ❌ | `gladia` | STT backend: `gladia`, `deepgram`, `null` |
| `llm_provider` | string | ❌ | `groq` | LLM backend: `groq`, `gemini`, `openai`, `null` |
| `llm_model` | string | ❌ | auto | LLM model name (e.g. `gemini-2.5-flash`) |
| `tts_provider` | string | ❌ | `uplift` | TTS backend: `uplift`, `elevenlabs`, `cartesia`, `null` |
| `tts_voice_id` | string | ❌ | `default` | TTS voice ID (provider-specific) |
| `sample_rate` | int | ❌ | `16000` | Client mic sample rate (Hz) — auto-resampled to 16 kHz |

---

## Audio Frame Format

### Inbound (Client → Server)

Send raw **PCM16 LE** audio as binary WebSocket frames.

| Property | Value |
|---|---|
| Format | 16-bit PCM, Little-Endian |
| Sample Rate | 16 kHz (or set `sample_rate` param) |
| Channels | 1 (Mono) |
| Frame Size | 320 bytes = 10 ms @ 16 kHz (recommended) |
| Max Frame | 512 KB (configurable via `WS_MAX_SIZE_BYTES`) |

```javascript
// Browser example — capture from getUserMedia
const context = new AudioContext({ sampleRate: 16000 });
const processor = context.createScriptProcessor(512, 1, 1);
processor.onaudioprocess = (e) => {
  const float32 = e.inputBuffer.getChannelData(0);
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768));
  }
  ws.send(int16.buffer);
};
```

### Outbound (Server → Client)

Binary frames contain raw **PCM16 LE** agent audio at **16 kHz**.

```javascript
ws.onmessage = (evt) => {
  if (evt.data instanceof ArrayBuffer) {
    // PCM16 agent audio — schedule for playback
    scheduleAudioChunk(evt.data);
  }
};
```

---

## Control Events (JSON)

All JSON messages are text frames. Every message has the structure:

```json
{
  "event_type": "<type>",
  "payload": { ... }
}
```

### Server → Client Events

#### `session_ready`
Emitted once after WebSocket upgrade and session initialization.
```json
{
  "event_type": "metric",
  "payload": {
    "kind": "session_ready",
    "session_id": "e5333b60-920b-4e30-9076-cf85ff771944"
  }
}
```

#### `transcript`
Emitted after each completed STT turn.
```json
{
  "event_type": "transcript",
  "payload": {
    "speaker": "user",
    "text": "What is the weather today?"
  }
}
```

#### `barge_in`
Emitted when the server detects and commits a barge-in (agent TTS cancelled).
```json
{
  "event_type": "barge_in",
  "payload": {
    "reason": "VAD speech during agent TTS"
  }
}
```

#### `latency`
Versioned per-turn telemetry emitted as stages become available and again after a correlated playback acknowledgement.
```json
{
  "event_type": "metric",
  "payload": {
    "kind": "latency",
    "schema_version": "1.0",
    "session_id": "00000000-0000-0000-0000-000000000001",
    "turn_id": "00000000-0000-0000-0000-000000000002",
    "clock_domain": "server_monotonic_ms",
    "client_clock_domain": "client_performance_ms",
    "measurement_quality": "server_ack_upper_bound",
    "timestamps_ms": {
      "acoustic_end": 1000.0,
      "vad_end": 1120.0,
      "stt_final": 1380.0,
      "server_send": 1650.0,
      "playback_ack_received": 1710.0,
      "client_playback_started": 8420.5
    },
    "durations_ms": {
      "vad_tail": 120.0,
      "stt_after_acoustic_end": 380.0,
      "user_perceived_e2e": 710.0
    },
    "missing_reasons": [],
    "slo": {"status": "provisional", "breached": null}
  }
}
```

Client timestamps are never subtracted from server monotonic timestamps. `server_ack_upper_bound` includes acknowledgement network delay. Missing anchors are `null`; the server does not substitute or cap measurements.

#### `vad_debug`
Emitted per audio frame when `UCVE_DEBUG_LISTENING=1` is set.
```json
{
  "event_type": "metric",
  "payload": {
    "kind": "vad_debug",
    "prob": 0.97,
    "speech_start": true,
    "speech_end": false,
    "rms": 0.042,
    "gated": false,
    "bytes": 640
  }
}
```

#### `ping`
```json
{"event_type": "ping", "interval_sec": 15}
```

### Client → Server Events

#### `pong` (required)
Must be sent in response to every `ping`.
```json
{"event_type": "pong", "t": 1726123456.789}
```

#### `text_turn` / `user_turn`
Inject a text utterance directly (bypasses STT). Useful for testing.
```json
{
  "event_type": "text_turn",
  "text": "Tell me a joke.",
  "system_prompt": "You are a funny AI."
}
```

#### `set_prompt`
Update the system prompt mid-session without reconnecting.
```json
{
  "event_type": "set_prompt",
  "system_prompt": "You are now a customer service agent for Acme Corp."
}
```

#### `barge_in` (client-initiated)
Client-side barge-in signal (e.g. from a UI stop button).
```json
{
  "event_type": "barge_in",
  "payload": {"reason": "user_pressed_stop"}
}
```

#### `control.playback_started`
Send once when the first scheduled audio source for the server-issued `turn_id` begins rendering.
```json
{
  "event_type": "control.playback_started",
  "payload": {
    "kind": "playback_started",
    "turn_id": "00000000-0000-0000-0000-000000000002",
    "client_clock_domain": "client_performance_ms",
    "client_playback_started_ms": 8420.5,
    "client_scheduled_playback_ms": 8418.2,
    "audio_context_time_sec": 12.45,
    "prebuffer_ms": 50.0,
    "underrun": false
  }
}
```

---

## WebSocket Close Codes

| Code | Reason | Description |
|---|---|---|
| `4401` | `missing token` | No JWT token in query params |
| `4401` | `invalid token` | JWT failed verification |
| `1001` | `pong timeout` | Client did not respond to ping |
| `1008` | `rate limit exceeded` | Too many frames per second |
| `1009` | `frame too large` | Binary frame exceeded max size |
| `1000` | — | Normal closure |
