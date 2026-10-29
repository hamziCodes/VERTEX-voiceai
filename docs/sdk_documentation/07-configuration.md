# Configuration Reference

Wavia is configured exclusively via **environment variables**. Copy `.env.example` to `.env` in the repository root to get started.

---

## Core Environment

| Variable | Default | Description |
|---|---|---|
| `UCVE_ENV` | `development` | Environment: `development`, `staging`, `production` |
| `UCVE_MINT_HMAC_SECRET` | `dev-mint-secret` | Secret for HMAC-signing session mint requests |
| `UCVE_DEMO_MODE` | auto | `1` = unauthenticated `/mint` allowed; auto-enabled in dev |
| `UCVE_ALLOWED_ORIGINS` | localhost list | Comma-separated CORS origin allowlist |
| `UCVE_METRICS_BEARER` | — | Bearer token required for `GET /metrics` |
| `UCVE_INITIAL_GREETING` | — | Agent greeting phrase spoken at session start |

---

## Provider API Keys

### STT
| Variable | Provider |
|---|---|
| `GLADIA_API_KEY` | Gladia (batch + live streaming) |
| `DEEPGRAM_API_KEY` | Deepgram (batch) |

### LLM
| Variable | Provider |
|---|---|
| `GROQ_API_KEY` | Groq |
| `GEMINI_API_KEY` | Google Gemini |
| `OPENAI_API_KEY` | OpenAI |

### TTS
| Variable | Provider |
|---|---|
| `UPLIFT_API_KEY` | Uplift (default) |
| `ELEVENLABS_API_KEY` | ElevenLabs |
| `CARTESIA_API_KEY` | Cartesia |

---

## Listening Pipeline (VAD / STT Feature Flags)

These env vars map to `ListeningPipelineConfig.from_env()` in `core/listening/config.py`.

| Variable | Default | Description |
|---|---|---|
| `UCVE_ENABLE_STREAMING_STT` | `true` | Use Gladia Live WebSocket for real-time STT |
| `UCVE_ENABLE_SPEECH_CAPTURE` | `true` | Use `SpeechCaptureEngine` (full V2 listening pipeline) |
| `UCVE_ENABLE_BARGE_VERIFY` | `true` | Enable barge-in verification engine |
| `UCVE_ENABLE_VAD_TIMING` | `true` | Apply per-language VAD hysteresis tuning |
| `UCVE_ENABLE_VAD_WORKER` | `false` | Run VAD in dedicated thread pool |
| `UCVE_ENABLE_FRAME_SLICING` | `true` | Slice large inbound audio chunks to 10ms frames |
| `UCVE_ENABLE_QUICK_WINS` | `false` | Phase 0 quick wins: endpoint delay + onset debounce |
| `UCVE_ENABLE_RAG_SPECULATIVE` | `false` | Trigger speculative RAG on STT partials |
| `UCVE_VAD_THRESHOLD` | `0.5` | Silero VAD speech probability threshold (0.0–1.0) |
| `UCVE_VAD_MIN_SPEECH_FRAMES` | `3` | Minimum consecutive speech frames to confirm onset |
| `UCVE_VAD_MIN_SILENCE_FRAMES` | `8` | Minimum consecutive silence frames to confirm end |
| `UCVE_GLADIA_ENDPOINTING` | `0.5` | Gladia Live STT silence duration (seconds) for final |
| `UCVE_GLADIA_RECEIVE_PARTIALS` | `true` | Receive partial transcripts from Gladia Live |
| `UCVE_STT_MOCK_TEXT` | — | Override STT with fixed test text (testing only) |
| `UCVE_DEBUG_LISTENING` | `false` | Emit per-frame VAD debug events to client |

---

## Speaking Pipeline (TTS Feature Flags)

These env vars map to `SpeakingPipelineConfig.from_env()` in `core/listening/config.py`.

| Variable | Default | Description |
|---|---|---|
| `UCVE_ENABLE_SPEAKING_HARDENING` | `true` | Enable chunk-size and scheduling hardening |
| `UCVE_TTS_CHUNK_SIZE_BYTES` | `3200` | TTS chunk size in bytes (160ms @ 16 kHz) |

---

## Database & Infrastructure

| Variable | Default | Description |
|---|---|---|
| `UCVE_DATABASE_URL` | — | PostgreSQL connection string (for pgvector RAG, sessions) |
| `UCVE_REDIS_URL` | `redis://localhost:6379` | Redis connection URL for session state |
| `UCVE_PG_POOL_MIN` | `1` | PostgreSQL connection pool minimum |
| `UCVE_PG_POOL_MAX` | `10` | PostgreSQL connection pool maximum |

---

## Compliance

| Variable | Default | Description |
|---|---|---|
| `UCVE_COMPLIANCE_TIER` | `standard` | Default tier: `standard`, `hipaa`, `gdpr_strict` |
| `UCVE_REDACT_PII` | `false` | Enable PII redaction in transcripts |

---

## Telephony

| Variable | Description |
|---|---|
| `TELNYX_API_KEY` | Legacy/platform key; controlled outbound uses tenant BYOK vault references |
| `UCVE_TELEPHONY_MEDIA_PUBLIC_URL` | Exact public `wss://` Telnyx media endpoint |
| `RUN_LIVE_TELEPHONY` | Explicit live-call gate; keep `0` by default |
| `TELNYX_APP_ID` | Telnyx TeXML application ID |
| `TELNYX_WEBHOOK_SECRET` | Webhook signature verification secret |

> **Note:** Twilio support was planned but is currently not implemented. The telephony_gateway uses Telnyx exclusively.

---

## Feature Flag Summary

| Flag | Status | Effect When Enabled |
|---|---|---|
| `UCVE_ENABLE_STREAMING_STT` | ✅ Default ON | Persistent Gladia WS socket per call |
| `UCVE_ENABLE_SPEECH_CAPTURE` | ✅ Default ON | Full V2 SpeechCaptureEngine |
| `UCVE_ENABLE_BARGE_VERIFY` | ✅ Default ON | 50–250ms barge-in verification window |
| `UCVE_ENABLE_VAD_TIMING` | ✅ Default ON | Per-language VAD hysteresis override |
| `UCVE_ENABLE_RAG_SPECULATIVE` | ❌ Default OFF | Speculative pgvector retrieval on partials |
| `UCVE_ENABLE_VAD_WORKER` | ❌ Default OFF | Thread-pool VAD isolation |
| `UCVE_DEBUG_LISTENING` | ❌ Default OFF | Per-frame debug events to client |

---

## `.env.example` Reference

The canonical example file is at `.env.example` in the repository root. It documents every supported variable with inline comments and safe defaults.
