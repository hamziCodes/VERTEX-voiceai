# Troubleshooting & Error Reference

---

## Common Startup Errors

### `Missing production secrets`
**Symptom:** Service crashes on startup with a missing secrets message.

**Cause:** `require_production_secrets()` checks that certain API keys are present when `UCVE_ENV != development`.

**Fix:** Set `UCVE_ENV=development` for local development, or provide all required provider API keys.

---

### `ModuleNotFoundError: No module named 'core'`
**Symptom:** Import error on any service start.

**Cause:** Package not installed in editable mode.

**Fix:**
```bash
pip install -e .
```

---

### `Error: Connection refused` on Worker Raw (port 8081)
**Symptom:** Health check to `http://127.0.0.1:8081/health` fails.

**Cause:** Worker Raw service is not running.

**Fix:** Start the worker:
```bash
python -m uvicorn worker_raw.main:app --host 127.0.0.1 --port 8081 --reload
```

---

## WebSocket Errors

### Close Code `4401` — Missing or Invalid Token
**Symptom:** WebSocket closes immediately after connect.

**Cause:** JWT token is missing, expired, or invalid.

**Fix:**
1. Verify the token is passed as `?token=<jwt>` in the WS URL
2. Mint a fresh token via `POST /mint`
3. Check `UCVE_MINT_HMAC_SECRET` matches between control plane and worker

---

### Close Code `1001` — Pong Timeout
**Symptom:** Connection drops after ~45 seconds of inactivity.

**Cause:** Client did not respond to `ping` events.

**Fix:** Implement pong response:
```javascript
ws.onmessage = (evt) => {
  if (typeof evt.data === 'string') {
    const msg = JSON.parse(evt.data);
    if (msg.event_type === 'ping') {
      ws.send(JSON.stringify({ event_type: 'pong', t: Date.now() / 1000 }));
    }
  }
};
```

---

### Close Code `1008` — Rate Limit Exceeded
**Symptom:** WebSocket closed with `rate limit exceeded` reason.

**Cause:** Client is sending audio frames too rapidly.

**Fix:** Send frames at the target cadence — 10ms frame every 10ms real-time.

---

### Close Code `1009` — Frame Too Large
**Symptom:** WebSocket closed with `frame too large` reason.

**Cause:** Binary frame exceeded `WS_MAX_SIZE_BYTES` (default: ~16MB).

**Fix:** Chunk audio into smaller frames (≤512 KB recommended, 320 bytes ideal).

---

## Audio Issues

### No Audio Playback (TTS Silent)
**Symptom:** No binary frames received from the server.

**Diagnosis checklist:**
1. Check server logs for `TTS PCM egress chunk` — if not present, TTS is not producing audio
2. Verify `UPLIFT_API_KEY` (or other TTS provider key) is set and valid
3. Check `peak_abs` in the log — if `0`, provider is returning silence/empty audio
4. Set `UCVE_TTS_PROVIDER=null` to test with silent provider and confirm pipeline reaches TTS stage

**Fix:** Verify provider API key and account quota.

---

### Garbled / Choppy Audio Playback
**Symptom:** Audio plays but sounds distorted or choppy.

**Cause:** Browser audio scheduling not respecting playback timeline.

**Fix:** Use a sequence-based `nextPlayTime` scheduler in the browser:
```javascript
let nextPlayTime = 0;
function scheduleChunk(pcm16Buffer) {
  const ctx = getAudioContext();
  const samples = new Int16Array(pcm16Buffer);
  const float32 = new Float32Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    float32[i] = samples[i] / 32768;
  }
  const buffer = ctx.createBuffer(1, float32.length, 16000);
  buffer.copyToChannel(float32, 0);
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(ctx.destination);
  const now = ctx.currentTime;
  if (nextPlayTime < now) nextPlayTime = now + 0.05;
  src.start(nextPlayTime);
  nextPlayTime += buffer.duration;
}
```

---

### Microphone Echo (Agent Hears Itself)
**Symptom:** The agent responds to its own TTS output, creating a feedback loop.

**Fix:** Implement Echo Guard in the browser — mute the microphone capture while the agent is playing audio:
```javascript
ws.onmessage = (evt) => {
  if (evt.data instanceof ArrayBuffer) {
    agentSpeakingGuard = true;
    // ... schedule and play audio ...
    setTimeout(() => { agentSpeakingGuard = false; }, estimatedDurationMs + 200);
  }
};
// In your audio capture callback:
if (agentSpeakingGuard) return; // Don't send mic frames
```

---

### STT Returns Empty / No Transcript
**Symptom:** User speaks but no LLM response; logs show empty speech buffer.

**Diagnosis:**
1. Check VAD is firing: look for `VAD speech_start` / `VAD speech_end` logs
2. Verify Gladia API key and quota
3. Enable debug VAD events: `UCVE_DEBUG_LISTENING=true`
4. Check mic sample rate matches — if sending 48 kHz, set `?sample_rate=48000` so the server resamples

---

## LLM Errors

### LLM Returns No Text / Tool Calls Only
**Symptom:** Agent is silent after user speech.

**Cause:** LLM emitted a tool call but no tool result fed back, leaving the pipeline suspended.

**Fix:** Ensure `ToolOrchestrator` handles the tool call and feeds result back. For testing, use `llm_provider=null`.

---

### High TTFT (LLM First Token Time > 500ms)
**Symptom:** `llm_ttft_ms` in latency waterfall is high.

**Recommendations:**
- Use `groq` provider (default) for lowest TTFT
- Reduce `max_tokens` in `LLMConfig` (default: 512)
- Reduce `history_token_budget` (default: 4096) if conversation history is very long

---

## Compliance Errors

### `InvalidStateTransitionError`
**Symptom:** Internal exception in logs.

**Cause:** Session FSM received an event that is illegal from the current state.

**Fix:** This is always a bug — check the recent turn sequence in logs. Common causes:
- Calling `run_turn` while FSM is still in `AGENT_SPEAKING`
- Duplicate barge-in signals

---

## Error Codes Reference

All structured error codes are in `core/errors/codes.py`.

| Code | Name | Description |
|---|---|---|
| `UCVE_001` | `PROVIDER_UNAVAILABLE` | STT/LLM/TTS provider returned an error |
| `UCVE_002` | `INVALID_SESSION_TOKEN` | JWT verification failed |
| `UCVE_003` | `RATE_LIMIT_EXCEEDED` | Client exceeded frame rate limit |
| `UCVE_004` | `FRAME_TOO_LARGE` | Audio frame exceeded max size |
| `UCVE_005` | `INVALID_STATE_TRANSITION` | FSM received illegal event |
| `UCVE_006` | `COMPLIANCE_VIOLATION` | Operation blocked by compliance policy |
| `UCVE_007` | `TENANT_NOT_FOUND` | Tenant ID does not exist |

---

## Debug Logging

Enable structured debug logging:

```env
UCVE_LOG_LEVEL=DEBUG
```

All logs are emitted as structured JSON via `core/observability/logging.py` (structlog-based).

Key log fields:
- `session_id` — correlates all events for a session
- `turn_id` — correlates a single STT→LLM→TTS turn
- `provider` — which STT/LLM/TTS provider handled the request
- `state` — current FSM state when the log was emitted

---

## Getting Support

1. Check logs with `session_id` filter for a full turn trace
2. Enable `UCVE_DEBUG_LISTENING=true` to get per-frame VAD events
3. Use the developer console at `http://localhost:8000/demo/` — it shows live latency waterfall and FSM state
4. Open an issue on the repository with the relevant log output and session ID
