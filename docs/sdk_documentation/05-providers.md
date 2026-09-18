# Provider Reference

Wavia uses a **provider abstraction layer** in `core/providers/` to allow swapping STT, LLM, and TTS backends without changing pipeline code.

---

## Architecture

All providers implement one of three abstract base classes:

| Interface | File | Key Method |
|---|---|---|
| `BaseSTTProvider` | `core/providers/interfaces/stt.py` | `transcribe_stream(audio_stream, config)` |
| `BaseLLMProvider` | `core/providers/interfaces/llm.py` | `generate_stream(messages, config)` |
| `BaseTTSProvider` | `core/providers/interfaces/tts.py` | `synthesize_stream(text, config)` |

Providers are registered globally at import time in `worker_raw/orchestration/pipeline.py`:

```python
ProviderRegistry.register_provider_class("gladia", GladiaSTTProvider)
ProviderRegistry.register_provider_class("deepgram", DeepgramSTTProvider)
ProviderRegistry.register_provider_class("groq", GroqLLMProvider)
ProviderRegistry.register_provider_class("gemini", GeminiLLMProvider)
ProviderRegistry.register_provider_class("openai", OpenAILLMProvider)
ProviderRegistry.register_provider_class("uplift", UpliftTTSProvider)
ProviderRegistry.register_provider_class("elevenlabs", ElevenLabsTTSProvider)
ProviderRegistry.register_provider_class("cartesia", CartesiaTTSProvider)
```

---

## Data Contracts

### `STTConfig`
```python
@dataclass
class STTConfig:
    language: str = "en"           # BCP-47 language code
    code_switching: bool = False   # Multi-language detection
    endpointing_seconds: float = 0.2
    sample_rate: int = 16000
```

### `Transcript`
```python
@dataclass(frozen=True)
class Transcript:
    text: str
    is_final: bool = False
    confidence: float | None = None
    language: str | None = None
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0
```

### `LLMConfig`
```python
@dataclass
class LLMConfig:
    model: str
    temperature: float = 0.7
    max_tokens: int = 512
    history_token_budget: int = 4096
    tools: list[ToolDefinition] = field(default_factory=list)
```

### `LLMStreamChunk`
```python
@dataclass(frozen=True)
class LLMStreamChunk:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    is_first_token: bool = False
```

### `TTSConfig`
```python
@dataclass
class TTSConfig:
    voice_id: str
    sample_rate: int = 22050   # Provider native rate; resampled to 16k by pipeline
    speed: float = 1.0
    encoding: str = "pcm16"
```

### `TTSChunk`
```python
@dataclass(frozen=True)
class TTSChunk:
    pcm_data: bytes
    native_sample_rate: int = 22050  # Resampled to 16k by EgressResampler
    is_final: bool = False
    timestamp_ms: float = 0.0
```

---

## STT Providers

### Gladia (Batch) — `gladia`
**File:** `core/providers/adapters/gladia_stt.py`

Sends buffered post-VAD audio to the Gladia REST API for batch transcription.

**Env vars:**
```env
GLADIA_API_KEY=your_key
```

### Gladia Live — `GladiaLiveSTTSession` (Streaming)
**File:** `core/providers/adapters/gladia_live_stt.py`

Maintains a persistent WebSocket connection to Gladia for real-time streaming transcription throughout the call. Returns `is_final=True` events using Gladia's endpointing. The pipeline prefers live finals over batch STT.

**Key config (from `ListeningPipelineConfig.from_env()`):**
```env
UCVE_ENABLE_STREAMING_STT=true
UCVE_GLADIA_ENDPOINTING=0.5         # seconds silence to trigger final
UCVE_GLADIA_RECEIVE_PARTIALS=true   # enables speculative RAG
```

### Deepgram — `deepgram`
**File:** `core/providers/adapters/deepgram_stt.py`

Batch transcription via Deepgram pre-recorded API.

**Env vars:**
```env
DEEPGRAM_API_KEY=your_key
```

---

## LLM Providers

### Groq — `groq`
**File:** `core/providers/adapters/groq_llm.py`

Default LLM provider. Uses Groq's OpenAI-compatible API for ultra-low TTFT.

**Env vars:**
```env
GROQ_API_KEY=your_key
```

**Default model:** `openai/gpt-oss-120b` (overridable per session)

### Gemini — `gemini`
**File:** `core/providers/adapters/gemini_llm.py`

Google Gemini via the Generative AI SDK.

**Env vars:**
```env
GEMINI_API_KEY=your_key
```

**Default model when selected:** `gemini-2.5-flash`

### OpenAI — `openai`
**File:** `core/providers/adapters/openai_llm.py`

Standard OpenAI chat completions (streaming).

**Env vars:**
```env
OPENAI_API_KEY=your_key
```

**Default model when selected:** `gpt-4o-mini`

---

## TTS Providers

### Uplift — `uplift`
**File:** `core/providers/adapters/uplift_tts.py`

Default TTS provider. Native 16 kHz PCM output; no resampling needed.

**Env vars:**
```env
UPLIFT_API_KEY=your_key
```

### ElevenLabs — `elevenlabs`
**File:** `core/providers/adapters/elevenlabs_tts.py`

High-quality voice synthesis. Audio is resampled to 16 kHz by `EgressResampler`.

**Env vars:**
```env
ELEVENLABS_API_KEY=your_key
```

**Voice selection:** Pass `tts_voice_id=<elevenlabs_voice_id>` in the WebSocket query.

### Cartesia — `cartesia`
**File:** `core/providers/adapters/cartesia_tts.py`

Low-latency streaming TTS.

**Env vars:**
```env
CARTESIA_API_KEY=your_key
```

---

## Failover Router

The `FailoverRouter` in `core/providers/failover.py` wraps TTS calls with a configurable timeout. If the primary provider fails or takes longer than `first_chunk_timeout` (default: 15 seconds), it retries with the secondary. On total failure, the pipeline falls back to `NullTTSProvider` (silence).

```python
await self.failover_router.call_with_failover(
    "tts", session_config.language, _invoke, first_chunk_timeout=15.0
)
```

---

## Selecting Providers Per-Session

Pass provider IDs as WebSocket query parameters:

```
ws://localhost:8081/ws/audio?token=...
  &stt_provider=deepgram
  &llm_provider=gemini
  &tts_provider=elevenlabs
  &tts_voice_id=rachel
```

Or programmatically via the Python SDK, TypeScript SDK, or directly via `PipelineSessionConfig`.

---

## Writing a Custom Provider

Implement the appropriate ABC, then register it:

```python
from core.providers.interfaces.tts import BaseTTSProvider, TTSConfig, TTSChunk
from core.providers.registry import ProviderRegistry

class MyTTSProvider(BaseTTSProvider):
    def health_check(self) -> bool:
        return True

    async def synthesize_stream(self, text: str, config: TTSConfig, ...):
        # yield TTSChunk objects
        yield TTSChunk(pcm_data=b"...", native_sample_rate=16000)

ProviderRegistry.register_provider_class("my_tts", MyTTSProvider)
```

Then select it: `ws://...?tts_provider=my_tts`
