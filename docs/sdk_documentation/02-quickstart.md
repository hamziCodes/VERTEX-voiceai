# Quickstart

Get Wavia running locally end-to-end in under 5 minutes.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.12+ |
| uv | Latest (`pip install uv`) |
| Redis | 6+ (local or Docker) |
| PostgreSQL | 14+ with pgvector (optional for RAG) |

> **Note:** For local demo use, Redis and PostgreSQL are not strictly required — the system uses in-memory stubs when not configured.

---

## 1. Clone & Install

```bash
git clone https://github.com/your-org/VERTEX_voiceai.git
cd VERTEX_voiceai

# Install all packages in editable mode
pip install -e .
```

---

## 2. Configure Environment

Copy the example env file and fill in your API keys:

```bash
cp .env.example .env
```

Minimum required variables for local development:

```env
# STT — Gladia (default)
GLADIA_API_KEY=your_gladia_key

# LLM — Groq (default)
GROQ_API_KEY=your_groq_key

# TTS — Uplift (default)
UPLIFT_API_KEY=your_uplift_key

# Session JWT signing secret
UCVE_MINT_HMAC_SECRET=dev-mint-secret

# Environment (enables unauthenticated /mint in demo mode)
UCVE_ENV=development

# Enables local-only prompt/provider overrides. Never enable in production.
UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES=1
```

Optional (ElevenLabs TTS, Cartesia TTS, Deepgram STT, Gemini LLM):

```env
ELEVENLABS_API_KEY=...
CARTESIA_API_KEY=...
DEEPGRAM_API_KEY=...
GEMINI_API_KEY=...
```

> **Twilio/telephony is not required** for the core voice pipeline and is currently flagged as optional infrastructure.

---

## 3. Start the Control Plane

```bash
python -m uvicorn control_plane.app:app --host 127.0.0.1 --port 8000 --reload
```

Verify:
```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","service":"control-plane"}
```

---

## 4. Start the Worker Node

In a second terminal:

```bash
python -m uvicorn worker_raw.main:app --host 127.0.0.1 --port 8081 --reload
```

Verify:
```bash
curl http://127.0.0.1:8081/health
# {"status":"ok","service":"worker-raw"}
```

---

## 5. Open the Demo Console

Navigate to:
```
http://127.0.0.1:8000/demo/
```

The demo console is served directly by the control plane from `examples/web-client/index.html`. It allows you to:

1. Mint a session JWT automatically
2. Connect a WebSocket to the worker node
3. Stream microphone audio
4. Hear real-time TTS responses
5. View live latency waterfall metrics

---

## 6. Mint a Session via API

For programmatic access:

```bash
curl -s -X POST http://127.0.0.1:8000/mint \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000001","agent_id":"00000000-0000-0000-0000-0000000000a1"}'
```

Response:
```json
{
  "status": "success",
  "session_id": "e5333b60-...",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

> `/mint` is only available in `UCVE_ENV=development`. In production, use the HMAC-signed `/v1/session` endpoint.

---

## 7. Connect a WebSocket

```javascript
const token = "<JWT from /mint>";
const ws = new WebSocket(`ws://127.0.0.1:8081/ws/audio?token=${token}`);
ws.onopen = () => ws.send(JSON.stringify({
  protocol_version: '1.0.0',
  event_id: crypto.randomUUID(),
  sequence: 1,
  event_type: 'protocol.hello',
  timestamp_ms: Date.now(),
  payload: {
    protocol_version: '1.0.0',
    sdk: { name: 'quickstart', version: '1.0.0' }
  }
}));
```

Send raw 16-bit PCM16 audio (16 kHz, mono) as binary frames:
```javascript
ws.send(pcmArrayBuffer);
```

Receive binary PCM16 audio for playback, and JSON control events:
```javascript
ws.onmessage = (evt) => {
  if (evt.data instanceof ArrayBuffer) {
    // Play PCM16 audio
  } else {
    const event = JSON.parse(evt.data);
    console.log(event.event_type, event.payload);
  }
};
```

---

## Next Steps

- [Session Lifecycle →](./03-session-lifecycle.md)
- [WebSocket Protocol →](./04-websocket-protocol.md)
- [Provider Reference →](./05-providers.md)
