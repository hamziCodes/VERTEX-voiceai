# UCVE SDK and Engine Documentation

Generated from the repository implementation, checked against code, config, tests, and existing docs. This document intentionally does not inspect `.env` or raw API key files. Line references point to the source files used as evidence.

## Evidence Notes

- Code is the authority when existing docs disagree with runtime behavior.
- "Implemented" means there is executable code in this repository.
- "Stub", "placeholder", or "roadmap" means the repository contains a named module or note but no production implementation.
- Runtime imports load `core/runtime/env.py`, which reads `.env`; this review used static file inspection instead.

## 1. Architecture & Core Sovereign Pipeline

### Core Runtime Shape

UCVE is organized around a sovereign realtime voice engine with these major services:

| Area | Primary modules | Responsibility |
| --- | --- | --- |
| Control plane | `control_plane/` | Session minting, JWT refresh, agents, usage, audit, secret rotation, metrics, admin routes |
| Raw worker | `worker_raw/` | Realtime WebSocket audio session, VAD, STT, RAG, LLM, tools, TTS, barge-in, client events |
| Managed worker | `worker_managed/` | Managed worker package present in repo |
| Telephony gateway | `telephony_gateway/`, `core/transport/` | Carrier webhooks, direct SIP, media transcoding, trunk routing |
| Core engine | `core/` | Types, FSM, listening pipeline, provider interfaces, provider adapters, buffers, latency, MCP, RAG, errors |
| Post-call | `post_call/` | Call record assembly, extraction, verification, webhook dispatch, memory status |
| SDKs | `sdk/python`, `sdk/typescript`, `sdk/flutter`, `sdk/shared` | Public client libraries and shared event schema |

### Canonical Audio Contract

The engine canonical audio format is defined in `core/types/constants.py:5`:

| Field | Value | Source |
| --- | --- | --- |
| Sample rate | `16000` Hz | `core/types/constants.py:5` |
| Channels | `1` mono | `core/types/constants.py:6` |
| Bytes per sample | `2` | `core/types/constants.py:7` |
| Frame samples | `512` | `core/types/constants.py:8` |
| Frame bytes | `1024` | `core/types/constants.py:9` |
| Frame duration | `32.0` ms | `core/types/constants.py:10` |

`AudioFrame` stores `pcm16`, `sample_rate`, `timestamp_ms`, `sequence`, `channel_count`, and optional `contains_speech`, with validation for even PCM16 length, positive sample rate, and positive channel count (`core/types/audio.py:27`). WAV serialization is available through `pcm16_to_wav` (`core/types/audio.py:59`).

`FrameSlicer` exists because Silero VAD requires exact 512-sample, 1024-byte windows. It emits only complete canonical frames and retains remainders until enough bytes arrive; `flush(pad=True)` pads the final frame (`core/listening/frame_slicer.py:1`).

Existing realtime protocol documentation says audio frames may be 320 or 640 bytes for 10 or 20 ms frames (`docs/sdk/REALTIME_PROTOCOL.md:10`). The running engine uses 1024-byte, 32 ms canonical frames for the VAD/listening pipeline. Integrators should send PCM16 mono audio and allow the worker to slice/resample into canonical windows.

### Input Validation, Resampling, and Buffering

The WebSocket worker accepts a query sample rate through `sample_rate` or `rate`, defaults to 16000 Hz, and constructs a `Resampler` if the client rate differs from 16000 (`worker_raw/ws_session.py:36`). Supported rates are `8000`, `16000`, `22050`, `24000`, `44100`, and `48000` (`core/types/resampler.py:7`).

The maximum inbound audio frame size is 256 KB (`worker_raw/ws_constants.py:5`). Oversized frames close the socket with code `1009`; rate limit rejection closes with `1008` (`worker_raw/ws_session.py:137`).

Default queue policies are in `core/buffers/policy.py`:

| Queue | Max size | Overflow policy | Source |
| --- | ---: | --- | --- |
| `inbound_mic` | 100 | `drop_oldest` | `core/buffers/policy.py:33` |
| `vad_internal` | 100 | `drop_oldest` | `core/buffers/policy.py:37` |
| `transcript_partial` | 200 | `drop_oldest` | `core/buffers/policy.py:41` |
| `outbound_tts` | 200 | `block` | `core/buffers/policy.py:45` |
| `sentence_bridge` | 50 | `drop_oldest` | `core/buffers/policy.py:49` |

`core/buffers/defaults.yaml:20` also defines `transcript_final` as unbounded with a high-watermark alert at 500.

### Listening Pipeline Configuration

The listening pipeline is feature-gated by `UCVE_PIPELINE_V2`, a comma-separated phase list. Known phase names are `quick_wins`, `frame_slicing`, `vad_timing`, `noise_gate`, `pre_roll`, `barge_verify`, `streaming_stt`, `speaking_hardening`, `tool_loop`, `rag_speculative`, `vad_worker`, and `production` (`core/listening/config.py:20`).

Default listening values:

| Setting | Default | Env var | Source |
| --- | ---: | --- | --- |
| VAD threshold | `0.5` | `UCVE_VAD_THRESHOLD` | `core/listening/config.py:82` |
| Min speech | `100` ms | `UCVE_VAD_MIN_SPEECH_MS` | `core/listening/config.py:87` |
| Min silence | `380` ms | `UCVE_VAD_MIN_SILENCE_MS` | `core/listening/config.py:88` |
| Pre-speech buffer | `200` ms | `UCVE_VAD_PRE_SPEECH_MS` | `core/listening/config.py:89` |
| Noise gate K | `3.0` | `UCVE_NOISE_GATE_K` | `core/listening/config.py:91` |
| Noise gate window | `50` frames | `UCVE_NOISE_GATE_WINDOW` | `core/listening/config.py:92` |
| Noise floor | `0.015` | `UCVE_NOISE_GATE_DEFAULT_FLOOR` | `core/listening/config.py:93` |
| Barge verify window | `700` ms | `UCVE_BARGE_VERIFY_WINDOW_MS` | `core/listening/config.py:95` |
| Barge sustained speech | `300` ms | `UCVE_BARGE_MIN_SUSTAINED_SPEECH_MS` | `core/listening/config.py:96` |
| Barge text backup | `3` words | `UCVE_BARGE_TEXT_BACKUP_WORDS` | `core/listening/config.py:97` |
| Gladia endpointing | `0.2` sec | `UCVE_GLADIA_ENDPOINTING` | `core/listening/config.py:99` |
| Gladia partials | `true` | `UCVE_GLADIA_RECEIVE_PARTIALS` | `core/listening/config.py:100` |
| Mock STT text | empty | `UCVE_STT_MOCK_TEXT` | `core/listening/config.py:101` |
| Debug listening | `false` | `UCVE_DEBUG_LISTENING` | `core/listening/config.py:102` |

Derived frame counts are computed with 32 ms frames. `vad_min_speech_frames`, `vad_min_silence_frames`, and `pre_speech_bytes` are computed in `core/listening/config.py:163`.

Default speaking values:

| Setting | Default | Env var | Source |
| --- | ---: | --- | --- |
| TTS chunk size | `8192` bytes | `UCVE_TTS_CHUNK_SIZE_BYTES` | `core/listening/config.py:200` |
| Egress prebuffer | `35` ms | `UCVE_EGRESS_PREBUFFER_MS` | `core/listening/config.py` |
| First-audio timeout | `3000` ms | `UCVE_TTS_FIRST_CHUNK_TIMEOUT_MS` | `core/listening/config.py` |
| Inter-chunk timeout | `3000` ms | `UCVE_TTS_INTER_CHUNK_TIMEOUT_MS` | `core/listening/config.py` |
| Overall TTS timeout | `30000` ms | `UCVE_TTS_OVERALL_TIMEOUT_MS` | `core/listening/config.py` |
| First chunk words | `2` | `UCVE_CHUNKER_FIRST_WORDS` | `core/listening/config.py` |
| Min chunk words | `3` | `UCVE_CHUNKER_MIN_WORDS` | `core/listening/config.py` |
| Tool filler delay | `400` ms | `UCVE_TOOL_FILLER_DELAY_MS` | `core/listening/config.py` |
| Debug latency | `false` | `UCVE_DEBUG_LATENCY` | `core/listening/config.py` |

### FSM States and Transitions

States are declared in `core/fsm/states.py:8`:

`CONNECTING`, `LISTENING`, `USER_SPEAKING`, `PROCESSING_INFERENCE`, `TOOL_EXECUTING`, `AGENT_SPEAKING`, `BARGE_IN_VERIFY`, `BARGE_IN_INTERRUPTED`, and `DISCONNECTED`.

Events are declared in `core/fsm/events.py:8`:

`session_admitted`, `vad_speech_start`, `vad_speech_end`, `stt_final`, `llm_first_token`, `tool_call_start`, `tool_result`, `tts_first_byte`, `tts_drained`, `barge_verify_timeout`, `barge_confirmed`, `barge_false_alarm`, `hangup`, and `disconnect`.

Runtime transitions are configured in `core/fsm/transitions.yaml:15`:

| From | Event | To |
| --- | --- | --- |
| `CONNECTING` | `session_admitted` | `LISTENING` |
| `LISTENING` | `vad_speech_start` | `USER_SPEAKING` |
| `LISTENING` | `stt_final` | `PROCESSING_INFERENCE` |
| `USER_SPEAKING` | `vad_speech_end` | `PROCESSING_INFERENCE` |
| `PROCESSING_INFERENCE` | `tts_first_byte` | `AGENT_SPEAKING` |
| `PROCESSING_INFERENCE` | `tool_call_start` | `TOOL_EXECUTING` |
| `TOOL_EXECUTING` | `tool_result` | `PROCESSING_INFERENCE` |
| `AGENT_SPEAKING` | `tts_drained` | `LISTENING` |
| `PROCESSING_INFERENCE` | `tts_drained` | `LISTENING` |
| `AGENT_SPEAKING` | `vad_speech_start` | `BARGE_IN_VERIFY` |
| `AGENT_SPEAKING` | `barge_confirmed` | `BARGE_IN_INTERRUPTED` |
| `BARGE_IN_VERIFY` | `barge_confirmed` | `BARGE_IN_INTERRUPTED` |
| `BARGE_IN_VERIFY` | `barge_false_alarm` | `AGENT_SPEAKING` |
| `BARGE_IN_VERIFY` | `barge_verify_timeout` | `AGENT_SPEAKING` |
| `BARGE_IN_INTERRUPTED` | `stt_final` | `PROCESSING_INFERENCE` |

### Barge-In and Three-Point Cancellation

Barge-in uses a pause/verify/commit model. `BargeVerifyEngine` observes VAD probability and partial transcript words during a 700 ms default verification window. It commits if sustained speech reaches 300 ms or partial transcript word count reaches 3 (`core/listening/barge_verify.py:33`). False alarms resume agent audio.

`ThreePointCancel` implements the hard cancellation contract: cancel active tasks, flush registered callbacks, and mark cancellation state (`core/fsm/cancel_contract.py:10`). The worker's immediate barge-in path cancels LLM/TTS, flushes queues, notifies the client, and transitions the FSM (`worker_raw/orchestration/pipeline.py:451`).

### Turn Pipeline

A normal worker turn follows this shape:

1. WebSocket session admits the tenant/session, triggers `SESSION_ADMITTED`, starts optional live Gladia STT, and sends a `session_ready` metric (`worker_raw/ws_session.py:75`).
2. Binary PCM frames are validated, resampled if needed, sliced into canonical frames if enabled, and placed into the inbound audio path (`worker_raw/ws_session.py:137`).
3. VAD and STT produce partial/final transcript events. Live STT partials can trigger speculative RAG; finals enqueue a turn (`worker_raw/orchestration/pipeline.py:482`).
4. Batch STT fallback uses `STTConfig(language=session_config.language, code_switching=True, endpointing_seconds=gladia_endpointing, sample_rate=16000)` (`worker_raw/orchestration/pipeline.py:648`).
5. The worker emits user transcript events, retrieves RAG context when available, streams LLM output, executes tools serially when requested, and streams TTS audio (`worker_raw/orchestration/pipeline.py:789`).
6. TTS uses `TTSConfig(voice_id=voice, sample_rate=16000)` in the worker path (`worker_raw/orchestration/pipeline.py:722`).
7. The latency waterfall is recorded and emitted as telemetry (`worker_raw/orchestration/pipeline.py:337`).

## 2. Provider Registry & Adapter Specs

### Provider Registry

Provider construction lives in `core/providers/factory.py`.

| Category | Supported IDs | Default | Source |
| --- | --- | --- | --- |
| STT | `gladia`, `deepgram` | `gladia` | `core/providers/factory.py:17` |
| LLM | `groq`, `gemini` | `groq` | `core/providers/factory.py:18` |
| TTS | `uplift`, `elevenlabs`, `cartesia` | `uplift` | `core/providers/factory.py:19` |

The factory normalizes unsupported category values back to defaults (`core/providers/factory.py:22`). Exported adapters include null adapters, Gladia, Deepgram, Groq, Gemini, Uplift, ElevenLabs, and Cartesia (`core/providers/adapters/__init__.py:18`).

### Provider Interfaces

| Interface | Config | Stream output |
| --- | --- | --- |
| VAD | `VADConfig(sample_rate=16000, window_samples=512, threshold=0.5, min_speech_frames=1, min_silence_frames=3)` | `VADEvent(speech_start, speech_end, probability)` |
| STT | `STTConfig(language="en", code_switching=False, endpointing_seconds=0.2, sample_rate=16000)` | `Transcript(text, is_final, confidence, language, start_time_ms, end_time_ms)` |
| LLM | `LLMConfig(model, temperature=0.7, max_tokens=512, history_token_budget=4096, tools=[])` | `LLMStreamChunk(text, tool_calls, finish_reason, is_first_token)` |
| TTS | `TTSConfig(voice_id, sample_rate=22050, speed=1.0, encoding="pcm16")` | `TTSChunk(pcm_data, native_sample_rate, is_final, timestamp_ms)` |
| S2S | `S2SConfig(voice_id="default", model="s2s-v1", language="en")` | `S2SEvent(audio_data, text, event_type, native_sample_rate)` |

Sources: `core/providers/interfaces/vad.py:11`, `core/providers/interfaces/stt.py:13`, `core/providers/interfaces/llm.py:13`, `core/providers/interfaces/tts.py:12`, `core/providers/interfaces/s2s.py:13`.

### VAD: Silero Adapter

`SileroVADProvider` is a hybrid ONNX plus energy fallback adapter. It expects the Silero ONNX model at `core/providers/adapters/silero_vad.onnx`, caps input at 512 KB, and uses CPU execution (`core/vad/silero_adapter.py:15`). If ONNX is unavailable, it falls back to energy detection with a default -45 dB threshold (`core/vad/silero_adapter.py:31`). VAD hysteresis is configured through threshold, min speech frames, and min silence frames (`core/vad/silero_adapter.py:68`).

### STT: Gladia

`GladiaSTTProvider` uses `PLATFORM_GLADIA_API_KEY` or `GLADIA_API_KEY`, default base URL `https://api.gladia.io`, and pre-recorded endpoint `/v2/pre-recorded` (`core/providers/adapters/gladia_stt.py:25`). It buffers at least 3200 bytes, caps at 512 KB, sends WAV content, and parses `result.transcription.full_transcript` or `prediction` (`core/providers/adapters/gladia_stt.py:75`). Mock mode is active when no key exists, `RUN_MOCK_PROVIDERS=1`, or `RUN_LIVE_PROVIDERS!=1` (`core/providers/adapters/gladia_stt.py:54`).

`GladiaLiveSTTSession` initializes Gladia live REST, then streams audio over the returned WebSocket and yields partial/final transcripts. It is disabled unless keys are present and `RUN_LIVE_PROVIDERS=1` (`core/providers/adapters/gladia_live_stt.py:1`).

### STT: Deepgram

`DeepgramSTTProvider` uses `PLATFORM_DEEPGRAM_API_KEY` or `DEEPGRAM_API_KEY`, default model `nova-3`, and endpoint `https://api.deepgram.com/v1/listen` (`core/providers/adapters/deepgram_stt.py:23`). It sends WAV audio with `Authorization: Token ...`, requests smart formatting and punctuation, and parses `results.channels[0].alternatives[0]` (`core/providers/adapters/deepgram_stt.py:75`). Mock mode follows the same no-key/mock/live-provider gates (`core/providers/adapters/deepgram_stt.py:58`).

### LLM: Groq

`GroqLLMProvider` uses `PLATFORM_GROQ_API_KEY` or `GROQ_API_KEY`, with default model `openai/gpt-oss-120b` and model aliases (`core/providers/adapters/groq_llm.py:20`). It speaks an OpenAI-compatible chat completions API, streams SSE `data:` lines, handles `[DONE]`, and assembles function tool-call fragments before returning a `tool_calls` finish (`core/providers/adapters/groq_llm.py:116`). Mock streaming emits words one by one when no key is present or live providers are disabled (`core/providers/adapters/groq_llm.py:96`).

### LLM: Gemini

`GeminiLLMProvider` defaults to `gemini-2.5-flash`, with aliases for `gemini`, `default`, `fast`, `gemini-2.5`, `gemini-2.0`, and `gemini-1.5` (`core/providers/adapters/gemini_llm.py:18`). It uses an OpenAI-compatible chat completions flow in the adapter (`core/providers/adapters/gemini_llm.py:135`).

### TTS: Uplift

`UpliftTTSProvider` uses `PLATFORM_UPLIFT_API_KEY` or `UPLIFT_API_KEY`, default base `https://api.upliftai.org`, default path `/v1/synthesis/text-to-speech`, and default output format `PCM_16000_16`. Voice resolution uses config voice ID, `UPLIFT_VOICE_ID`, `PLATFORM_UPLIFT_VOICE_ID`, then `v_meklc281`. Live synthesis reads the HTTP body incrementally, emits the first audio bytes immediately, and parses variable RIFF/WAVE chunks without discarding valid PCM (`core/providers/adapters/uplift_tts.py`).

### TTS: ElevenLabs

`ElevenLabsTTSProvider` uses `PLATFORM_ELEVENLABS_API_KEY`, `ELEVENLABS_API_KEY`, or `ELEVEN_API_KEY`; default voice is `hpp4J3VqNfWAUOO0d1Us` (`core/providers/adapters/elevenlabs_tts.py:16`). It calls `/v1/text-to-speech/{voice_id}/stream`, defaults model to `eleven_multilingual_v2`, defaults output to `pcm_16000`, and streams even-byte chunks (`core/providers/adapters/elevenlabs_tts.py:48`).

### TTS: Cartesia

`CartesiaTTSProvider` uses `PLATFORM_CARTESIA_API_KEY` or `CARTESIA_API_KEY`, default voice `f786b574-daa5-4673-aa0c-cbe3e8534c02`, API `https://api.cartesia.ai/tts/bytes`, version `2025-04-16`, and model `sonic-2` (`core/providers/adapters/cartesia_tts.py:16`). It skips punctuation-only text, applies a simple Arabic-script language hint, requests raw `pcm_s16le`, and streams even-byte chunks (`core/providers/adapters/cartesia_tts.py:87`).

### Null Providers

Null adapters are implemented for tests and safe offline behavior. `NullTTS` emits one silent final PCM16 chunk, `NullSTT` yields empty transcript output, `NullLLM` yields an empty stop chunk, `NullVAD` emits no speech, and `NullS2S` emits empty audio events (`core/providers/adapters/nulls.py:15`).

### Failover, Circuit Breaking, and Demotion

`CircuitBreakerConfig` defaults to five consecutive failures, 50 percent error-rate threshold, rolling window size 10, and 30 second cooldown (`core/providers/circuit_breaker.py:17`). `ProviderHealthState` opens on consecutive failure threshold or error-rate threshold and transitions to half-open after cooldown (`core/providers/failover.py:16`).

`FailoverRouter` defaults priority to `["primary", "secondary"]` and calls providers with a first-chunk timeout default of 15 seconds. It records latency, success, and failure and raises `NoProviderAvailableError` when every candidate is unavailable (`core/providers/failover.py:70`). The `subsequent_chunk_timeout` parameter exists in the signature but is not used by the shown implementation (`core/providers/failover.py:85`).

Latency demotion counts over-budget turns and triggers only when `slo_policy.enforce_demotion` is true (`core/latency/demotion.py:11`).

### Language Profiles

Profiles are loaded from `core/language/profiles/*.yaml` through `LanguageRegistry` (`core/language/registry.py:36`).

| Language | VAD silence | Voice | First chunk words | Direction | Code switching | Redaction | CS mode |
| --- | ---: | --- | ---: | --- | --- | --- | --- |
| `en` | 500 ms | `cartesia-en-v1` | 3 | `ltr` | true | full | enforced |
| `ur` | 800 ms | `ur-standard-1` | 2 | `rtl` | false | regex_partial | enforced |
| `ar` | 800 ms | `ar-multilingual-1` | 2 | `rtl` | false | regex_partial | measure-only |
| `ms` | 500 ms | `cartesia-ms-v1` | 3 | `ltr` | false | full | measure-only |

Sources: `core/language/profiles/en.yaml:1`, `core/language/profiles/ur.yaml:1`, `core/language/profiles/ar.yaml:1`, `core/language/profiles/ms.yaml:1`.

## 3. Complete SDK Reference

### Python SDK

Package metadata:

| Field | Value | Source |
| --- | --- | --- |
| Package | `ucve-voice-sdk` | `sdk/python/pyproject.toml:5` |
| Version | `1.0.0` | `sdk/python/pyproject.toml:6` |
| Python | `>=3.10` | `sdk/python/pyproject.toml:10` |
| Dependencies | `websockets>=12.0`, `pydantic>=2.5.0`, `httpx>=0.25.0` | `sdk/python/pyproject.toml:12` |

`UCVEVoiceClient` is a zero-secret browser/client style SDK. The constructor accepts:

```python
UCVEVoiceClient(
    token: str,
    ws_url: str = "ws://localhost:8081/ws/audio",
    stt_provider: str = "gladia",
    llm_provider: str = "groq",
    tts_provider: str = "cartesia",
    on_transcript=None,
    on_audio=None,
    on_metric=None,
    **kwargs,
)
```

Source: `sdk/python/ucve/client.py:22`.

Security behavior:

- Empty tokens are rejected.
- `api_key`, `secret`, `private_key`, and `tenant_secret` kwargs are rejected.
- The SDK sends a short-lived session token, not raw provider credentials.

Connection behavior:

- `connect()` appends `token`, `stt_provider`, `llm_provider`, and `tts_provider` query params to `ws_url`, opens the WebSocket, and starts `_listen_loop` (`sdk/python/ucve/client.py:59`).
- Binary server messages are passed to `on_audio`.
- JSON `transcript` events are passed to `on_transcript`.
- JSON `metric` events are passed to `on_metric`.
- `send_audio(pcm16_bytes)` sends raw binary audio (`sdk/python/ucve/client.py:109`).
- `emit_playback_started()` sends `control.playback_started` with timestamp and kind (`sdk/python/ucve/client.py:115`).
- `send_barge_in(rms=0.08)` sends sequenced `control.barge_in` correlated to the active turn.
- `on_clear_audio` clears application-owned playout and may return played milliseconds; the SDK automatically sends `control.clear_audio_ack`.
- `emit_playback_drained()` confirms normal client playout completion.
- `on_played_text_commit` receives the assistant context boundary accepted by the server.
- `disconnect()` cancels the listener and closes the socket (`sdk/python/ucve/client.py:135`).

Minimal Python use:

```python
import asyncio
from ucve import UCVEVoiceClient

async def main():
    client = UCVEVoiceClient(
        token="SESSION_JWT",
        ws_url="ws://localhost:8081/ws/audio",
        on_transcript=lambda event: print(event),
        on_metric=lambda event: print(event),
    )
    await client.connect()
    await client.send_audio(b"\x00\x00" * 512)
    await client.disconnect()

asyncio.run(main())
```

### TypeScript SDK

Package metadata:

| Field | Value | Source |
| --- | --- | --- |
| Package | `@ucve/voice-sdk` | `sdk/typescript/package.json:2` |
| Version | `1.0.0` | `sdk/typescript/package.json:3` |
| Build | `tsc` | `sdk/typescript/package.json:8` |
| Test | `jest` | `sdk/typescript/package.json:9` |
| React peer | `>=18` optional | `sdk/typescript/package.json:17` |

`UCVEVoiceClientOptions` includes:

- `wsUrl`
- `sttProvider`
- `llmProvider`
- `ttsProvider`
- `onTranscript`
- `onAudio`
- `onMetric`
- `onError`

Source: `sdk/typescript/src/client.ts:5`.

The static version manifest is:

```ts
{
  apiVersion: "1.0.0",
  eventSchemaVersion: "1.0.0",
  minServerVersion: "0.1.0",
}
```

Source: `sdk/typescript/src/client.ts:22`.

Security behavior rejects empty tokens and forbidden option keys `apiKey`, `api_key`, `secret`, and `privateKey` (`sdk/typescript/src/client.ts:28`).

Connection behavior:

- `connect()` builds the WebSocket URL and appends `token`, `stt_provider`, `llm_provider`, and `tts_provider` as query params (`sdk/typescript/src/client.ts:47`).
- Binary messages are converted to `Int16Array` and sent to `onAudio`.
- JSON `transcript` events are sent to `onTranscript`.
- JSON `metric` events are sent to `onMetric`.
- `sendAudioChunk()` sends an `ArrayBuffer` or `Uint8Array` (`sdk/typescript/src/client.ts:101`).
- `emitPlaybackStarted()` sends `control.playback_started` (`sdk/typescript/src/client.ts:108`).
- `sendBargeIn(rms=0.08)` sends sequenced `control.barge_in` for the active turn.
- `onClearAudio` clears application-owned playout and returns played milliseconds for the automatic acknowledgment.
- `emitPlaybackDrained()` confirms normal client playout completion.
- `onPlayedTextCommit` receives the server-accepted assistant context boundary.
- `disconnect()` closes the socket (`sdk/typescript/src/client.ts:128`).

Minimal TypeScript use:

```ts
import { UCVEVoiceClient } from "@ucve/voice-sdk";

const client = new UCVEVoiceClient("SESSION_JWT", {
  wsUrl: "ws://localhost:8081/ws/audio",
  onTranscript: (event) => console.log(event),
  onMetric: (event) => console.log(event),
});

await client.connect();
client.sendAudioChunk(new Int16Array(512).buffer);
client.disconnect();
```

### React Hook

`useUCVEVoice()` returns `isConnected`, `isSpeaking`, `transcript`, `connect(token, options?)`, `disconnect()`, and `sendBargeIn()` (`sdk/typescript/src/hooks/useUCVEVoice.ts:8`). The hook appends transcript text for incoming transcript events and clears `isSpeaking` on explicit barge-in (`sdk/typescript/src/hooks/useUCVEVoice.ts:23`). It does not currently toggle `isSpeaking` based on server playback events.

### Flutter SDK

The Flutter SDK is present as a stub. `UCVEVoiceClient` stores `token` and `wsUrl`, rejects empty tokens, and exposes `connect()` and `disconnect()` placeholders (`sdk/flutter/lib/ucve_voice_client_stub.dart:1`). `sdk/flutter/ROADMAP.md:1` classifies Flutter SDK integration as a roadmap item for v1, non-blocking.

### Shared Event Schema

The shared schema defines:

| Event | Payload | Source |
| --- | --- | --- |
| `control.pong` | required `t` number | `sdk/shared/event_schema.json:7` |
| `control.playback_started` | required `t`, optional `kind` | `sdk/shared/event_schema.json:22` |
| `control.barge_in` | `turn_id`, monotonic `sequence`, optional `rms`/`t` | `sdk/shared/event_schema.json` |
| `control.clear_audio` / `_ack` | `turn_id`, `sequence`; ack adds `played_audio_ms` | `sdk/shared/event_schema.json` |
| `control.playback_drained` | `turn_id`, `played_audio_ms` | `sdk/shared/event_schema.json` |
| `assistant.played_text_commit` | `turn_id`, text, played duration, completeness | `sdk/shared/event_schema.json` |
| `text.turn` | required `text` | `sdk/shared/event_schema.json:54` |
| `transcript` | `speaker` enum `user` or `agent`, `text` | `sdk/shared/event_schema.json:70` |
| `metric` | `event`, `waterfall` object | `sdk/shared/event_schema.json:86` |
| Session events | `session_ready`, `audio_start`, `audio_stop`, `info`, `error` | `sdk/shared/event_schema.json:101` |

Runtime caveat: the worker accepts `text_turn` and `user_turn`, while the shared schema declares `text.turn` (`worker_raw/ws_session.py:173`, `sdk/shared/event_schema.json:54`). SDK public clients do not currently expose a first-class text-turn helper.

### Realtime WebSocket Protocol

Endpoint:

```text
ws://<host>:8081/ws/audio?token=<JWT>&stt_provider=<id>&llm_provider=<id>&tts_provider=<id>
```

Source: `docs/sdk/REALTIME_PROTOCOL.md:3` and `worker_raw/main.py:100`.

Client -> server:

| Kind | Format | Notes |
| --- | --- | --- |
| Audio | Binary PCM16 | Prefer 16 kHz mono; other supported rates may be declared via query and resampled |
| `control.pong` | JSON | Responds to server ping |
| `control.ping` | JSON | Worker responds with pong |
| `control.playback_started` | JSON | Client tells server audio playback reached user |
| `control.barge_in` | JSON | Client requests barge-in with active turn and sequence |
| `control.clear_audio_ack` | JSON | Confirms scheduled audio was stopped and reports played duration |
| `control.playback_drained` | JSON | Confirms an uninterrupted turn finished rendering |
| `text_turn` / `user_turn` | JSON | Runtime text turn aliases |
| `set_prompt` | JSON | Runtime prompt update |

Server -> client:

| Kind | Format | Notes |
| --- | --- | --- |
| Audio | Binary PCM16 | TTS output |
| `transcript` | JSON | User or agent transcript |
| `metric` | JSON | Session-ready, latency waterfall, debug events |
| `ping` | JSON | Server keepalive |
| `control.barge_in` | JSON | Committed interruption with turn and sequence |
| `control.clear_audio` | JSON | Requires immediate client playout clear and acknowledgment |
| `audio_end` | JSON | Marks that server egress is drained for the turn |
| `assistant.played_text_commit` | JSON | Text admitted to conversation history |

The ping loop sends a control ping every 20 seconds and closes with code `1001` on pong timeout (`worker_raw/ws_constants.py:7`, `worker_raw/ws_session.py:282`).

## 4. Control Plane & Telephony APIs

### Control Plane Mounts and Middleware

`control_plane/app.py` builds the FastAPI app, configures CORS origins from `UCVE_ALLOWED_ORIGINS`, and defaults to local development origins (`control_plane/app.py:68`). Middleware sets `X-Request-Id` and derives `request.state.tenant_id` from the `X-Tenant-Id` header (`control_plane/app.py:126`).

Routers mounted under `/v1` include telephony, extraction schemas, knowledge bases, alerts, and agents (`control_plane/app.py:108`).

### Core Control Plane Endpoints

| Method | Path | Purpose | Source |
| --- | --- | --- | --- |
| GET | `/health` | Health check | `control_plane/app.py:136` |
| GET | `/` | Redirect to `/demo/` | `control_plane/app.py:141` |
| GET | `/json/version` | Service/version metadata | `control_plane/app.py:147` |
| POST | `/v1/session` | HMAC or API-key session mint | `control_plane/app.py:156` |
| POST | `/mint` | Demo/API-key quick mint | `control_plane/app.py:197` |
| POST | `/v1/session/mint` | Demo/API-key quick mint | `control_plane/app.py:197` |
| POST | `/v1/session/refresh` | Refresh session JWT | `control_plane/app.py:239` |
| GET | `/v1/usage` | Tenant usage and quota | `control_plane/app.py:247` |
| GET | `/v1/audit` | Audit event query | `control_plane/app.py:278` |
| POST | `/v1/secrets/rotate` | Rotate provider secret | `control_plane/app.py:293` |
| GET | `/metrics` | Prometheus metrics, bearer protected | `control_plane/app.py:311` |

OpenAPI and docs routes are explicitly registered at `/openapi.json`, `/docs`, and `/redoc` (`control_plane/openapi_serve.py:19`).

### Session Minting

`POST /v1/session` accepts:

- `X-Tenant-Id`
- `X-Timestamp`
- `X-Nonce`
- `X-Agent-Id`
- `X-Signature`
- optional `Origin`
- optional `Referer`
- optional `Authorization: Bearer <api_key>`

Source: `control_plane/app.py:156`.

HMAC signature payload is:

```text
{tenant_id}.{timestamp}.{nonce}.{agent_id}
```

with HMAC-SHA256 hex digest (`control_plane/auth/hmac_mint.py:18`). Timestamp max age defaults to 60 seconds (`control_plane/auth/hmac_mint.py:26`). Nonces are stored for 60 seconds to block replay (`control_plane/routes/session.py:121`).

Mint flow:

1. Enforce rate limit, default 120 per minute (`control_plane/routes/session.py:28`).
2. Verify HMAC unless API-key minting is used (`control_plane/routes/session.py:117`).
3. Reject replayed nonce (`control_plane/routes/session.py:121`).
4. Resolve tenant; in dev/test, unknown tenants are auto-provisioned (`control_plane/routes/session.py:125`).
5. Reject cross-tenant agent use (`control_plane/routes/session.py:135`).
6. Check allowed origin unless API-key minting is used (`control_plane/routes/session.py:151`).
7. Check quota and add `X-UCVE-Quota-Warning: soft_cap` when applicable (`control_plane/routes/session.py:155`).
8. Check runtime capacity (`control_plane/routes/session.py:168`).
9. Create session, issue JWT, acquire quota, and return status, session ID, token, TTL, and WebSocket URL (`control_plane/routes/session.py:175`).

JWT issuance uses HS256, `action="roomJoin"`, `iat`, and `exp`; default TTL is 120 seconds (`control_plane/auth/jwt.py:35`). Verification requires `exp`, `iat`, `sub`, and `action`, and rejects any action other than `roomJoin` (`control_plane/auth/jwt.py:56`).

API keys use prefix `ucve_live_`, SHA256 hashes, scopes, and roles (`control_plane/auth/api_keys.py:11`).

### Agent Control APIs

The agents router is mounted at `/v1/agents` (`control_plane/routes/agents.py:18`).

| Method | Path | Purpose | Source |
| --- | --- | --- | --- |
| POST | `/v1/agents` | Create agent | `control_plane/routes/agents.py:53` |
| GET | `/v1/agents` | List agents | `control_plane/routes/agents.py:78` |
| GET | `/v1/agents/{agent_id}` | Get agent | `control_plane/routes/agents.py:88` |
| PATCH | `/v1/agents/{agent_id}/autosave` | Autosave patch | `control_plane/routes/agents.py:102` |
| POST | `/v1/agents/{agent_id}/publish` | Publish version | `control_plane/routes/agents.py:126` |
| GET | `/v1/agents/{agent_id}/versions` | List versions | `control_plane/routes/agents.py:147` |
| GET | `/v1/agents/{agent_id}/versions/{version}` | Get version | `control_plane/routes/agents.py:160` |
| POST | `/v1/agents/{agent_id}/pin` | Pin session to version | `control_plane/routes/agents.py:175` |

`AgentConfig` stores persona, languages, provider routes, tools, MCP servers, knowledge bases, extraction schema, pronunciation lexicon, telephony, compliance, version, and publish status (`control_plane/agents/models/agent_config.py:15`). Provider route models support category, language, route priority, model, and enabled state (`control_plane/agents/models/provider_config.py:8`).

### Additional Control Plane Routes

| Method | Path | Purpose | Source |
| --- | --- | --- | --- |
| POST | `/v1/telephony/calls` | Authenticated, policy-gated single outbound call | `control_plane/routes/telephony.py` |
| POST | `/v1/extraction-schemas` | Create extraction schema | `control_plane/routes/extraction_schemas.py:12` |
| GET | `/v1/knowledge-bases/status/{tenant_id}` | Placeholder KB status | `control_plane/routes/knowledge_bases.py:10` |
| GET | `/v1/alerts/{tenant_id}` | List the tenant's operational alerts (quota, capacity, provider chain) | `control_plane/routes/alerts.py` |

Usage currently returns quota and zeroed usage totals (`control_plane/routes/usage.py:8`). Audit queries are tenant-scoped unless role is `platform_admin` (`control_plane/audit_routes.py:10`). Secret rotation endpoint returns a success message after RBAC checks (`control_plane/secrets_routes.py:12`).

### Telephony Gateway

The standalone telephony gateway exposes:

| Method | Path | Purpose | Source |
| --- | --- | --- | --- |
| GET | `/health` | Health check | `telephony_gateway/main.py:19` |
| GET | `/` | Service metadata | `telephony_gateway/main.py:24` |
| POST | `/v1/telephony/webhooks/telnyx` | Exact-body Ed25519 Telnyx webhook admission | `telephony_gateway/main.py` |

`WebhookNormalizer` supports Telnyx and Twilio. Telnyx event names are mapped into answered, ended, and DTMF categories using carrier payload fields (`telephony_gateway/webhook_normalizer.py:20`). Twilio maps `CallStatus` values such as `in-progress`, `answered`, `completed`, `canceled`, `failed`, and `busy` (`telephony_gateway/webhook_normalizer.py:46`).

Telnyx signature verification is fail-closed. It checks required headers, timestamp drift default 300 seconds, Ed25519 signatures when a 32-byte public key is available, and HMAC-SHA256 fallback for hex or base64 signatures (`telephony_gateway/telnyx/signature.py:10`).

### Trunks and SIP

`SIPTrunkConfig` models known provider and role values, priority, enabled state,
region, credential reference, connection ID, and trunk ID. Readiness requires an
enabled supported adapter plus both the credential reference and connection ID.

`TrunkFailoverRouter` sorts tenant trunks by priority and fails closed unless a
supported trunk is explicitly healthy and fully configured. Secondary selection
is only for new calls; established calls are never migrated transparently.

`DirectSIPTransport` performs inbound RTP mu-law decode, 8 kHz to 16 kHz resampling, and rebuffering into 512-sample canonical frames. Egress down-samples 16 kHz PCM16 to 8 kHz and encodes mu-law (`core/transport/direct_sip.py:19`).

`LiveKitSIPTransport` is gated by `UCVE_ENABLE_LIVEKIT_SIP=="true"` (`core/transport/livekit_sip.py:12`). Twilio Media Streams and Generic PTA adapters are present as stubs or minimal adapters (`telephony_gateway/adapters/twilio_media_stream.py:10`, `telephony_gateway/adapters/generic_pta.py:10`).

### Outbound and Supervisor Features

The repository contains a controlled, authenticated single-call Telnyx Dial path
with tenant policy, durable idempotency, spend/rate/concurrency caps, and a
separate live-call gate. It does not contain campaigns, batch contact ingestion,
predictive dialing, answering-machine detection, supervisor whisper, or true
carrier warm transfer. `escalate_to_human` remains a tool result, not a telephony
transfer feature.

## 5. Post-Call Intelligence & Memory Engine

### Call Record Assembly

`PostCallAssembler.assemble()` builds a `CallRecord` from tenant ID, agent ID, session ID, turns, caller ID, timestamps, end reason, transport type, recording URI, compliance tier, and metrics (`post_call/pipeline/assembler.py:20`). It maps turn data to `DiarizedTurn`, suppresses recording URI for `gdpr_strict` and `zero_retention`, creates recording metadata, and marks `memory_embed_status` as `pending` (`post_call/pipeline/assembler.py:38`).

`CallRecord` fields include call/session identity, caller ID, start/end times, end reason, transport type, disposition, turns, recording, redacted transcript reference, raw transcript reference, compliance tier, metrics snapshot, and memory embedding status (`post_call/models/call_record.py:17`).

### Extraction Schemas

`TenantExtractionSchema` contains schema ID, tenant ID, name, fields, and `max_fields=50`; it rejects schemas whose field count exceeds the max (`post_call/extraction/schema.py:20`). Each field has name, type, description, and required flag (`post_call/extraction/schema.py:11`).

`ExtractionService.extract()` validates HIPAA BAA acknowledgement for HIPAA tiers, validates schema max fields, and returns field values when field names or descriptions appear in the transcript text. Otherwise it returns `None` for that field (`post_call/extraction/service.py:17`).

### Verification

`VerificationService` checks:

- Low confidence against `min_confidence_threshold=0.75`.
- Missing required fields.
- Invalid phone fields.
- Invalid datetime fields.

Source: `post_call/verification/service.py:25`.

Phone normalization strips to E.164-ish output, defaults 10-digit local numbers to country code `1`, and rejects digit lengths outside 10 to 15 (`post_call/verification/phone.py:6`). Datetime parsing accepts ISO strings and converts `Z` to UTC (`post_call/verification/datetime.py:8`).

### Webhook Dispatch

`TenantWebhookTarget` requires URL and secret (`post_call/webhook/targets.py:9`). `WebhookDispatcher` signs payloads with HMAC-SHA256, sends `X-UCVE-Signature` and `X-Idempotency-Key`, retries up to three times, and backs off with powers of two seconds (`post_call/webhook/dispatcher.py:28`).

### Post-Call Worker

`PostCallWorker.process_record()` performs extraction, verification, review queue insertion for issues, summary generation, CRM payload construction, and webhook dispatch only when a target exists and there are no verification issues (`post_call/worker.py:43`). The CRM payload includes call ID, tenant ID, caller ID, extracted data, issues count, summary, disposition, and idempotency key (`post_call/worker.py:52`).

### DLQ and Retry Sweeper

`DeadLetterJob` tracks job ID, tenant ID, job type, payload reference, error code, attempts, max attempts, created timestamp, and expiration 30 days out (`core/errors/dlq.py:13`). The DLQ repo can enqueue jobs, return pending retries, and purge expired records (`core/errors/dlq.py:29`).

`worker_jobs/dlq_retry_sweeper.py` increments attempts for pending jobs and purges expired jobs. It does not execute the original failed job payload (`worker_jobs/dlq_retry_sweeper.py:11`).

### Longitudinal Memory

`LongitudinalMemoryEmbedder.process_call_record_memory()` marks a call as skipped if there are no turns and no redacted transcript reference; otherwise it marks memory embedding complete (`core/rag/memory/longitudinal.py:10`). No vector embedding generation is implemented in this module.

## 6. Tooling, MCP & Speculative RAG

### MCP Host and Transports

`MCPServerConfig` supports transports `streamable_http`, `sse`, and `stdio`, with endpoint, allowed tools, and credentials reference (`core/mcp/host.py:14`). Tool calls use a default timeout of 3000 ms and fallback utterance "Let me check on that and get back to you" (`core/mcp/host.py:22`).

`MCPHost.call_tool()` wraps execution in an async timeout and returns an error result with fallback content on timeout (`core/mcp/host.py:74`). Streamable HTTP and SSE transports are implemented as lightweight call stubs (`core/mcp/transports/streamable_http.py:6`, `core/mcp/transports/sse.py:6`). Stdio transport is blocked unless `UCVE_MCP_ALLOW_STDIO=true` (`core/mcp/transports/stdio.py:1`).

### Built-In Tools and Orchestration

Built-in tools:

| Tool | Purpose | Required params | Source |
| --- | --- | --- | --- |
| `end_conversation_summary` | End call with summary/disposition payload | `summary` | `core/mcp/builtin_tools.py:35` |
| `escalate_to_human` | Request human escalation payload | `reason` | `core/mcp/builtin_tools.py:48` |

`ToolOrchestrator` combines built-ins and connected MCP hosts, executes tool calls serially, frames tool responses as `role="tool"`, and marks `data_framed=True` (`core/mcp/orchestrator.py:19`).

Tool filler behavior starts a timer and emits "Checking that for you..." after 400 ms unless cancelled (`core/mcp/filler.py:10`). Timeout fallback returns both an error and a spoken fallback phrase (`core/mcp/timeout_fallback.py:8`).

### Speculative RAG

`SpeculativeRetrieval` retrieves against partial transcript text and reconciles against the final transcript with normalized Levenshtein distance. If the distance is at or below the default threshold `0.08`, speculative results are reused; otherwise final transcript retrieval is performed (`core/rag/speculative.py:41`).

The worker only uses speculative RAG when the phase flag is enabled and a retriever exists (`worker_raw/orchestration/pipeline.py:523`).

### RAG Models, Ingestion, Retrieval, and Embedder Policy

RAG models:

| Model | Fields | Source |
| --- | --- | --- |
| `ChunkConfig` | `chunk_size_tokens=400`, `chunk_overlap_tokens=64` | `core/rag/models.py:10` |
| `KnowledgeBaseSource` | tenant ID, source type, URI, source ID, refresh interval | `core/rag/models.py:18` |
| `KnowledgeBaseChunk` | tenant ID, text, chunk ID, source document ID, embedding, metadata | `core/rag/models.py:29` |

Ingestion supports `pdf_upload`, `faq_list`, and fallback raw content sources (`core/rag/ingestion/worker.py:12`). PDF chunking converts token budgets to approximate word windows using a 0.75 multiplier and emits metadata source `pdf` plus word count (`core/rag/ingestion/chunkers/pdf.py:9`). FAQ chunking emits `Q: ...\nA: ...` text and metadata source `faq` (`core/rag/ingestion/chunkers/faq.py:10`).

`PgVectorRetriever` can use DB-backed retrieval with tenant RLS through `SET LOCAL app.current_tenant_id`, or an in-memory mock chunk list when no DB pool is supplied (`core/rag/retriever.py:21`). `QdrantRetriever` is currently a stub returning an empty list (`core/rag/adapters/qdrant.py:1`).

Cloud embedding is blocked for `hipaa` and `gdpr_strict` tiers; otherwise it requires tenant opt-in (`core/rag/embedder_policy.py:6`).

## 7. System Diagnostics, Errors & Configuration Reference

### Error Codes

`UCVEErrorCode` declares:

`AUTH_INVALID`, `AUTH_EXPIRED`, `QUOTA_EXCEEDED`, `PROVIDER_TIMEOUT`, `PROVIDER_UNAVAILABLE`, `FSM_INVALID_TRANSITION`, `BARGE_IN_FAILED`, `HIPAA_BAA_REQUIRED`, `DATA_CLASSIFICATION_BLOCKED`, `WEBHOOK_SIGNATURE_INVALID`, `TRUNK_UNAVAILABLE`, `CALLER_ID_MISSING`, `EXTRACTION_FAILED`, `DISPATCH_FAILED`, `REVIEW_REQUIRED`, `LATENCY_SLO_BREACH`, and `INTERNAL_ERROR` (`core/errors/codes.py:8`).

Structured HTTP mapping covers auth, quota, provider timeout/unavailable, FSM invalid transition, HIPAA BAA, webhook signature invalid, trunk unavailable, extraction failure, dispatch failure, and internal error. Unmapped codes default to HTTP 500 (`core/errors/structured.py:11`).

Client-facing mapper returns generic safe messages for selected codes and never exposes raw internals (`core/errors/client_mapper.py:8`). Redaction recursively redacts keys containing token, secret, password, ssn, dob, transcript, audio_data, and phi (`core/errors/redaction.py:7`).

### Metrics and Latency

Prometheus metrics implemented:

| Metric | Type | Source |
| --- | --- | --- |
| `ucve_turn_latency_ms` | Histogram | `core/observability/metrics.py:89` |
| `ucve_barge_in_total` | Counter | `core/observability/metrics.py:92` |
| `ucve_provider_failover_total` | Counter | `core/observability/metrics.py:95` |
| `ucve_buffer_drop_total` | Counter | `core/observability/metrics.py:98` |

`/metrics` is protected by `Authorization: Bearer <UCVE_METRICS_BEARER>` and returns Prometheus text (`control_plane/app.py:311`).

Default latency budgets:

| Stage | Warn | Budget | Source |
| --- | ---: | ---: | --- |
| STT | 150 ms | 250 ms | `core/latency/collector.py:15` |
| RAG | 100 ms | 200 ms | `core/latency/collector.py:16` |
| LLM TTFT | 200 ms | 400 ms | `core/latency/collector.py:17` |
| TTS TTFB | 150 ms | 250 ms | `core/latency/collector.py:18` |

SLO policy defaults are p50 target 450 ms, p95 target 850 ms, demotion disabled, and alerts enabled (`core/latency/slo_policy.py:8`). The worker emits latency waterfall metrics containing turn ID, STT, LLM TTFT, TTS TTFB, RAG, and total end-to-end milliseconds (`worker_raw/orchestration/pipeline.py:337`).

The observability log schema requires timestamp, level, and event; optional fields include call ID, tenant ID, session ID, phase, latency, provider ID, and error code (`core/observability/schema.json:1`).

### Runtime Profiles and Admission

`RuntimeProfileName` supports `dev`, `standard`, and `high_density` (`core/runtime/profile_loader.py:14`). Profiles define max sessions per worker, Silero pool size, worker tasks, Redis memory, Postgres pool, max provider streams, RAM, and vCPU (`core/runtime/profile_loader.py:20`). `UCVE_RUNTIME_PROFILE` defaults to `dev`, and missing profiles fall back to dev (`core/runtime/profile_loader.py:34`).

`SessionAdmissionController` enforces runtime capacity by tracking active session IDs against the selected profile's max sessions per worker (`core/runtime/admission.py:21`).

### Production Secret Validation

`UCVE_ENV` defaults to development (`core/runtime/env.py:42`). Production mode is active only when `UCVE_ENV=="production"` (`core/runtime/env.py:47`). In production, `UCVE_JWT_SECRET`, `UCVE_MINT_HMAC_SECRET`, and `UCVE_METRICS_BEARER` are required and validated against insecure defaults (`core/runtime/env.py:76`).

### Configuration Reference

The example environment file documents these public configuration names. Values below are defaults or blanks from `.env.example`; actual `.env` was not read.

| Category | Variables | Source |
| --- | --- | --- |
| Runtime | `UCVE_ENV`, `UCVE_RUNTIME_PROFILE`, `RUN_LIVE_PROVIDERS` | `.env.example:10` |
| Control secrets | `UCVE_JWT_SECRET`, `UCVE_MINT_HMAC_SECRET`, `UCVE_METRICS_BEARER` | `.env.example:21` |
| WebSocket/CORS | `UCVE_WS_PUBLIC_URL`, `UCVE_ALLOWED_ORIGINS` | `.env.example:26` |
| Data stores | `DATABASE_URL`, `REDIS_URL` | `.env.example:38` |
| LLM providers | `PLATFORM_GROQ_API_KEY`, `GOOGLE_API_KEY`, `PLATFORM_OPENAI_API_KEY`, `PLATFORM_ANTHROPIC_API_KEY` | `.env.example:47` |
| STT providers | `PLATFORM_GLADIA_API_KEY`, `PLATFORM_DEEPGRAM_API_KEY`, `PLATFORM_SONIOX_API_KEY` | `.env.example:62` |
| TTS providers | `PLATFORM_UPLIFT_API_KEY`, `UPLIFT_VOICE_ID`, `PLATFORM_UPLIFT_VOICE_ID`, `UPLIFT_OUTPUT_FORMAT`, `PLATFORM_ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `PLATFORM_ELEVENLABS_VOICE_ID`, `ELEVENLABS_OUTPUT_FORMAT`, `ELEVENLABS_MODEL_ID`, `PLATFORM_CARTESIA_API_KEY`, `CARTESIA_API_KEY`, `CARTESIA_VOICE_ID`, `CARTESIA_MODEL_ID`, `CARTESIA_SAMPLE_RATE`, `CARTESIA_VERSION`, `PLATFORM_RIME_API_KEY`, `PLATFORM_FISH_AUDIO_API_KEY` | `.env.example:74` |
| Telephony | `TELNYX_PUBLIC_KEY`, `UCVE_TELEPHONY_MEDIA_PUBLIC_URL`, `RUN_LIVE_TELEPHONY`, tenant BYOK credential/trunk records, optional LiveKit variables | `.env.example` |
| KMS/cloud | `AWS_KMS_KEY_ID`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `GCP_KMS_KEY_NAME`, `GOOGLE_APPLICATION_CREDENTIALS` | `.env.example:130` |
| Observability | `OTEL_EXPORTER_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `SENTRY_DSN` | `.env.example:142` |
| Pipeline phases | `UCVE_PIPELINE_V2` | `.env.example:147` |
| Listening | `UCVE_VAD_THRESHOLD`, `UCVE_VAD_MIN_SPEECH_MS`, `UCVE_VAD_MIN_SILENCE_MS`, `UCVE_VAD_PRE_SPEECH_MS`, `UCVE_NOISE_GATE_K`, `UCVE_NOISE_GATE_WINDOW`, `UCVE_NOISE_GATE_DEFAULT_FLOOR`, `UCVE_BARGE_VERIFY_WINDOW_MS`, `UCVE_BARGE_MIN_SUSTAINED_SPEECH_MS`, `UCVE_BARGE_TEXT_BACKUP_WORDS`, `UCVE_GLADIA_ENDPOINTING`, `UCVE_GLADIA_RECEIVE_PARTIALS`, `UCVE_STT_MOCK_TEXT` | `.env.example:155` |
| Speaking | `UCVE_TTS_CHUNK_SIZE_BYTES`, `UCVE_EGRESS_PREBUFFER_MS`, `UCVE_TTS_FIRST_CHUNK_TIMEOUT_MS`, `UCVE_TTS_INTER_CHUNK_TIMEOUT_MS`, `UCVE_TTS_OVERALL_TIMEOUT_MS`, `UCVE_CHUNKER_FIRST_WORDS`, `UCVE_CHUNKER_MIN_WORDS`, `UCVE_TOOL_FILLER_DELAY_MS`, `UCVE_DEBUG_LISTENING`, `UCVE_DEBUG_LATENCY`, `UCVE_INITIAL_GREETING` | `.env.example` |

### Known Integration Caveats

- Engine canonical frames are 1024 bytes and 32 ms, while `docs/sdk/REALTIME_PROTOCOL.md` still documents 320/640-byte client frames.
- Shared event schema declares `text.turn`; runtime worker accepts `text_turn` and `user_turn`.
- Flutter SDK is a stub/roadmap item.
- Qdrant retriever is a stub.
- Twilio Media Streams adapter is a stub.
- LiveKit SIP is feature-gated and disabled unless explicitly enabled.
- Outbound campaign dialing, predictive dialing, answering-machine detection, supervisor whisper, and real carrier warm transfer are not production implemented in the repository.
- DLQ retry sweeper increments attempts and purges expired records but does not replay original job payloads.
