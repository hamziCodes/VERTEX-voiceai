# Runbook: Voice Pipeline V2 Tuning

Operational guide for UCVE production voice pipeline feature flags and tuning knobs. Full spec: `docs/developer/PRODUCTION_VOICE_PIPELINE_UPGRADE_PLAN.md` §8.

## Master feature flag

| Variable | Default | Effect |
|---|---|---|
| `UCVE_PIPELINE_V2` | *(empty)* | Legacy demo pipeline |
| `UCVE_PIPELINE_V2=production` | — | Enables all V2 phases at once |

**Phase tokens** (comma-separated): `quick_wins`, `frame_slicing`, `vad_timing`, `noise_gate`, `pre_roll`, `barge_verify`, `streaming_stt`, `speaking_hardening`, `tool_loop`, `rag_speculative`, `vad_worker`, `production`.

Recommended rollout: enable phases incrementally in dev/staging before setting `production` in prod.

## Enabling production mode

1. Copy tuning vars from `.env.example` §11 into root `.env`.
2. Set provider keys and live mode:
   ```bash
   RUN_LIVE_PROVIDERS=1
   PLATFORM_GLADIA_API_KEY=...
   PLATFORM_GROQ_API_KEY=...
   PLATFORM_UPLIFT_API_KEY=...
   ```
3. Enable full V2 stack:
   ```bash
   UCVE_PIPELINE_V2=production
   ```
4. Restart `worker_raw` (uvicorn on port 8081).

## Tuning knobs

### VAD & noise gate

| Variable | Default | Notes |
|---|---|---|
| `UCVE_VAD_THRESHOLD` | `0.5` | Silero speech probability |
| `UCVE_VAD_MIN_SPEECH_MS` | `100` | Onset debounce |
| `UCVE_VAD_MIN_SILENCE_MS` | `380` | Endpoint hangover |
| `UCVE_VAD_PRE_SPEECH_MS` | `200` | Pre-roll captured before onset |
| `UCVE_NOISE_GATE_K` | `3.0` | RMS multiplier above noise floor |
| `UCVE_NOISE_GATE_WINDOW` | `50` | Frames for floor estimation |
| `UCVE_NOISE_GATE_DEFAULT_FLOOR` | `0.015` | Initial floor when idle |

**Symptom → knob:** false `[USER]` transcripts → raise `UCVE_VAD_MIN_SILENCE_MS` or lower `UCVE_VAD_THRESHOLD`. Chopped utterances → lower `UCVE_VAD_MIN_SILENCE_MS`.

### Barge-in

| Variable | Default | Notes |
|---|---|---|
| `UCVE_BARGE_VERIFY_WINDOW_MS` | `700` | Pause before committing interrupt |
| `UCVE_BARGE_MIN_SUSTAINED_SPEECH_MS` | `300` | Min speech to confirm barge |
| `UCVE_BARGE_TEXT_BACKUP_WORDS` | `3` | STT partial word count backup |

Requires `barge_verify` or `production` in `UCVE_PIPELINE_V2`.

### STT (Gladia)

| Variable | Default | Notes |
|---|---|---|
| `UCVE_GLADIA_ENDPOINTING` | `0.2` | Seconds of silence before final |
| `UCVE_GLADIA_RECEIVE_PARTIALS` | `true` | Stream partial transcripts |
| `UCVE_STT_MOCK_TEXT` | *(empty)* | Dev-only mock text; leave empty in prod |

Requires `streaming_stt` or `production` for live WebSocket STT.

### Speaking / TTS egress

| Variable | Default | Notes |
|---|---|---|
| `UCVE_TTS_CHUNK_SIZE_BYTES` | `8192` | Uplift batch size |
| `UCVE_TTS_POP_SKIP_BYTES` | `2048` | Skip initial pop artifact |
| `UCVE_EGRESS_PREBUFFER_MS` | `35` | Server-side egress prebuffer |
| `UCVE_CLIENT_PREBUFFER_CHUNKS` | `3` | Web client jitter buffer |

Requires `speaking_hardening` or `production`.

### LLM chunking & tools

| Variable | Default | Notes |
|---|---|---|
| `UCVE_CHUNKER_FIRST_WORDS` | `2` | Early TTS chunk trigger |
| `UCVE_CHUNKER_MIN_WORDS` | `3` | Minimum words per chunk |
| `UCVE_TOOL_FILLER_DELAY_MS` | `400` | Filler phrase before tool call |
| `UCVE_INITIAL_GREETING` | *(empty)* | Optional TTS phrase on session admit |

## Debug telemetry

| Variable | Default | Effect |
|---|---|---|
| `UCVE_DEBUG_LISTENING=1` | `0` | Per-frame VAD metrics to client |
| `UCVE_DEBUG_LATENCY=1` | `0` | Per-turn latency waterfall in worker logs |

Use sparingly in production (log volume).

## Verify with web client

1. Start control plane (`8000`) and worker (`8081`).
2. Open `examples/web-client/index.html` (or serve locally).
3. Click **Start Session** — expect `session_ready` and optional greeting.
4. **Silence test:** stay quiet 15 s → zero `[USER]` lines.
5. **Speech test:** say a full sentence → one clean `[USER]` transcript.
6. **Playback test:** agent response shows `AUDIO_IN` activity and audible output.
7. **Barge test** (with `barge_verify`): cough → agent resumes; say "wait stop" → agent stops.
8. End session → clean WebSocket close.

Quick automated gate:

```bash
python -m pytest tests/listening/ -v --tb=short
python -m pytest tests/hardening/test_h5_pipeline_e2e.py -v --tb=short
python -m pytest voice_engine_plan/tests/phase_tests/test_phase_17_pipeline_integration.py -v --tb=short
```

## Rollback

No code deploy required — flags are env-only:

1. Set `UCVE_PIPELINE_V2=` (empty) in `.env`.
2. Restart `worker_raw`.
3. Legacy pipeline paths activate immediately.

Confirm rollback: silence test should behave as before V2; check worker startup logs for empty phase set.

## Telephony note

SIP ingress (μ-law → 16 kHz PCM) and egress (16 kHz PCM → μ-law) are wired in `DirectSIPTransport` and `TelnyxDirectSIPAdapter`. RTP packetization to the carrier is still hooked via `on_mulaw_egress` callback — validate PSTN legs separately before prod traffic.
