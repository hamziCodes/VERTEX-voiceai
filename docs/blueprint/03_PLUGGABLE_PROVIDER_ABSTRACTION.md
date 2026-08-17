# 03 — Pluggable Provider Abstraction

File 3 of 9. This is the interface layer that every legacy repo except `habiba-sdk-agent` lacked. AUDIT_01 §1 states it plainly for v3: "There is **no** STT/LLM/TTS interface layer. Concrete classes are constructed inside `SessionOrchestrator.__init__`." Multilingual has interfaces defined but doesn't use them for STT/LLM (AUDIT_03 §6: "Interfaces exist but orchestrator still instantiates Gladia/Groq concretely"). Habiba is the only repo with a real provider registry (AUDIT_04 §6, Modularity 8/10 justification #1). This file generalizes habiba's registry pattern and multilingual's TTS-failover pattern into one abstraction covering all four provider categories plus S2S.

---

## 1. Design Principles

1. **Interfaces are enforced, not decorative.** Multilingual's `Protocol` classes existing-but-unused (AUDIT_03 §6) is the failure mode to avoid — the orchestrator/pipeline core must depend only on the abstract types below, never import a concrete provider class directly outside the registry's construction site.
2. **Capability tables, not boolean flags.** Habiba's `capabilities.py` maps `(language, provider_type) → status ∈ {enabled, testing, absent}` (AUDIT_04 §2 STT/LLM/TTS tables) rather than a single global "does this repo support X" flag — this is more expressive and is adopted as the canonical capability model.
3. **Fallback is a first-class routing concern, not a per-provider try/except.** Multilingual's `TTSManager` (timeout failover + 60s circuit breaker, AUDIT_03 §1) is the only legacy implementation of this and is generalized to STT and LLM too, since AUDIT_05 §1 matrix shows STT/LLM retry as `NOT IMPLEMENTED / ABSENT` in three of four repos.

---

## 2. Python Interfaces (Pydantic + ABC)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Protocol
from pydantic import BaseModel, Field
from enum import Enum


class ProviderCapabilityStatus(str, Enum):
    ENABLED = "enabled"
    TESTING = "testing"      # habiba's `fish_audio: testing` pattern, AUDIT_04 §2 TTS
    ABSENT = "absent"


class AudioEncoding(str, Enum):
    PCM16 = "pcm16"
    MULAW = "mulaw"
    OPUS = "opus"


# ---------------------------------------------------------------------------
# VAD
# ---------------------------------------------------------------------------

class VADConfig(BaseModel):
    threshold: float = 0.55                 # v3 default, AUDIT_01 §2 VAD
    min_speech_duration_ms: int = 250        # v3 default (AUDIT_01 §2); multilingual
                                              # also tunes speech onset — see AUDIT_03 §2
    min_silence_duration_ms: int = 250       # v3 default (AUDIT_01 §2); multilingual
                                              # uses language overrides / unused
                                              # `vad_silence_commit_ms=600` (AUDIT_03 §2)
                                              # rather than this as a shared constant
    sample_rate: int = 16000
    window_samples: int = 512
    language_silence_overrides: dict[str, int] = Field(default_factory=dict)
    # multilingual's per-language override (ur/ar: 800ms), AUDIT_03 §2 VAD


class BaseVADProvider(ABC):
    @abstractmethod
    async def feed(self, frame: bytes) -> "VADEvent | None":
        """Returns an event only on a state *transition*, NOT every speech
        frame. v3's `feed()` returns True **only on speech-start**
        (`silero_service.py:117–121`; AUDIT_01 §2) — it does not emit
        speech-end. UCVE emits both `speech_start` and `speech_end` so
        turn-commit does not have to infer offset from silence counters
        alone."""

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...


class VADEvent(BaseModel):
    type: str  # "speech_start" | "speech_end"
    timestamp_ms: float
    confidence: float | None = None


# ---------------------------------------------------------------------------
# STT
# ---------------------------------------------------------------------------

class STTConfig(BaseModel):
    languages: list[str]                     # e.g. ["ur", "en"] — v3 AUDIT_01 §2
    code_switching: bool = False             # default False per habiba's measured
                                              # Urdu CER (AUDIT_04 §2 VAD:
                                              # "CER 0.14 vs 0.43 with ur+en");
                                              # per-language/tenant override still
                                              # allowed — File 4 §1. Was True in an
                                              # earlier draft; corrected during
                                              # finalization pass to match File 4/8.
    endpointing_seconds: float = 0.2          # v3 + multilingual Gladia agree, AUDIT_01/03 §2
    sample_rate: int = 16000
    encoding: AudioEncoding = AudioEncoding.PCM16


class Transcript(BaseModel):
    text: str
    is_final: bool
    language: str | None = None
    confidence: float | None = None          # UCVE turn manager consumes this when
                                              # present. Live v3 `GladiaTranscript`
                                              # (`gladia_service.py:63–70`) has
                                              # `language` but **no** `confidence`
                                              # field; orchestrator never reads
                                              # `language` (`websocket.py:234–299`).
                                              # MULTI `interfaces.Transcript` declares
                                              # optional `confidence` but Gladia never
                                              # fills it. Habiba persist/SDK emit
                                              # `{role,text,at}` / `{text,final,speaker}`
                                              # with no confidence. Treat as optional.


class BaseSTTProvider(ABC):
    @abstractmethod
    async def start_session(self, config: STTConfig) -> None: ...

    @abstractmethod
    async def send_audio(self, frame: bytes) -> None: ...

    @abstractmethod
    def transcripts(self) -> AsyncIterator[Transcript]: ...

    @abstractmethod
    async def stop_session(self) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: dict  # JSON Schema


class LLMConfig(BaseModel):
    model: str
    system_instruction: str
    temperature: float = 0.7                # v3 hardcoded 0.7, AUDIT_01 §2 — now configurable
    max_output_tokens: int = 1000            # v3: 1000; multilingual: 150 (AUDIT_03 §5
                                              # notes this causes truncation risk vs v3) —
                                              # UCVE default is per-deployment, not hardcoded
    tools: list[ToolDefinition] = Field(default_factory=list)
    history_token_budget: int = 4000         # replaces both legacy list-length prunes
                                              # (File 2 §4)


class LLMStreamChunk(BaseModel):
    delta_text: str | None = None
    tool_call: dict | None = None
    finish_reason: str | None = None


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_stream(
        self, messages: list[dict], config: LLMConfig
    ) -> AsyncIterator[LLMStreamChunk]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

class TTSConfig(BaseModel):
    voice_id: str
    sample_rate: int = 22050                 # v3/multilingual output rate, AUDIT_01/03 §2
    encoding: AudioEncoding = AudioEncoding.PCM16
    connect_timeout_s: float = 3.0           # v3 default, AUDIT_01 §2 TTS
    read_timeout_s: float = 8.0
    max_retries: int = 1                     # v3 default; see failover model below
                                              # for cross-provider retry instead
    # Optional SSML-style hints — deferred (File 4 §5); not day-one required.
    rate: str | None = None                  # e.g. "slow" for digit sequences
    pitch: str | None = None
    emphasis_spans: list[tuple[int, int]] | None = None


class CancellationToken(Protocol):
    """Minimal cancel surface checked at producer/queue/transport
    (File 2 §3.3). Concrete impl may wrap asyncio.Event."""

    def is_cancelled(self) -> bool: ...
    def cancel(self) -> None: ...


class BaseTTSProvider(ABC):
    @abstractmethod
    async def synthesize_stream(
        self, text: str, config: TTSConfig, cancel_token: CancellationToken
    ) -> AsyncIterator[bytes]:
        """Streams raw PCM chunks. Must honor cancel_token at every yield
        (File 2 §3.3 atomicity requirement)."""

    @abstractmethod
    async def health_check(self) -> bool: ...


# ---------------------------------------------------------------------------
# Speech-to-Speech (multimodal, direct)
# ---------------------------------------------------------------------------

class S2SConfig(BaseModel):
    model: str                               # e.g. "gemini-2.0-flash-live",
                                              # "gpt-4o-realtime-preview"
    voice_id: str
    system_instruction: str
    tools: list[ToolDefinition] = Field(default_factory=list)
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000


class BaseSpeechToSpeechProvider(ABC):
    """`[NEW]` — no legacy repo implements S2S (AUDIT_05 §3 gap analysis does
    not even list it as a checked-for gap because none of the four repos
    approach this architecture; it is added here as a forward-looking path
    per the master mandate's latency target, File 1 §4)."""

    @abstractmethod
    async def send_audio(self, frame: bytes) -> None: ...

    @abstractmethod
    def receive_events(self) -> AsyncIterator["S2SEvent"]: ...

    @abstractmethod
    async def interrupt(self) -> None:
        """S2S providers typically have native interruption support —
        this should map to the same BARGE_IN_INTERRUPTED state (File 2 §2)
        rather than bypassing the FSM."""

    @abstractmethod
    async def health_check(self) -> bool: ...


class S2SEvent(BaseModel):
    type: str  # "audio_delta" | "transcript_delta" | "tool_call" | "turn_complete"
    audio: bytes | None = None
    text: str | None = None
    tool_call: dict | None = None
```

---

## 3. TypeScript Type Definitions (client SDK mirror)

```typescript
export type ProviderCapabilityStatus = "enabled" | "testing" | "absent";

export interface STTConfig {
  languages: string[];
  codeSwitching: boolean; // default false — mirror Python STTConfig / File 4 §1
  endpointingSeconds: number;
  sampleRate: number;
  encoding?: "pcm16" | "mulaw" | "opus";
}

export interface Transcript {
  text: string;
  isFinal: boolean;
  language?: string;
  confidence?: number;
}

export interface LLMConfig {
  model: string;
  systemInstruction: string;
  temperature: number;
  maxOutputTokens: number;
  tools: ToolDefinition[];
  historyTokenBudget?: number;
}

export interface ToolDefinition {
  name: string;
  description: string;
  parametersSchema: Record<string, unknown>;
}

export interface TTSConfig {
  voiceId: string;
  sampleRate: number;
  encoding?: "pcm16" | "mulaw" | "opus";
  connectTimeoutS: number;
  readTimeoutS: number;
  maxRetries?: number;
  rate?: string;
  pitch?: string;
  emphasisSpans?: Array<[number, number]>;
}

// Client SDK does not implement providers directly — it consumes the
// unified event stream from the transport gateway (File 1 §3.4). These
// types exist so the Agent Builder UI (File 8) can render provider
// capability tables without a backend round-trip per keystroke.
export interface ProviderCapabilityEntry {
  providerId: string;
  category: "stt" | "llm" | "tts" | "vad" | "s2s";
  language: string;
  status: ProviderCapabilityStatus;
  notes?: string;  // e.g. habiba's measured CER rationale, AUDIT_04 §2
}
```

---

## 4. Provider Registry

```python
class ProviderRegistry:
    """Generalizes habiba's registry.py (AUDIT_04 §6) to all four categories
    plus S2S. No silent fallback at construction time — AUDIT_04 §6
    Modularity justification #1 explicitly credits habiba's registry for
    having 'no silent fallback', which UCVE preserves: an unconfigured
    provider raises at startup, not at first request."""

    def __init__(self, capability_table: list["ProviderCapabilityEntry"]):
        self._capability_table = capability_table
        self._stt: dict[str, type[BaseSTTProvider]] = {}
        self._llm: dict[str, type[BaseLLMProvider]] = {}
        self._tts: dict[str, type[BaseTTSProvider]] = {}
        self._vad: dict[str, type[BaseVADProvider]] = {}
        self._s2s: dict[str, type[BaseSpeechToSpeechProvider]] = {}

    def register_stt(self, provider_id: str, impl: type[BaseSTTProvider]) -> None: ...
    def register_llm(self, provider_id: str, impl: type[BaseLLMProvider]) -> None: ...
    def register_tts(self, provider_id: str, impl: type[BaseTTSProvider]) -> None: ...

    def resolve(
        self, category: str, language: str, preferred: str | None = None
    ) -> str:
        """Looks up the capability table (habiba's capabilities.py pattern,
        AUDIT_04 §2) to find an `enabled` provider for (category, language).
        Falls back through a configured priority order, never silently to
        `testing`-status providers unless explicitly opted in."""
```

---

## 5. Dynamic Provider Hot-Swapping / Fallback

### 5.1 Generalized from multilingual's TTS failover

Multilingual's `TTSManager` is the only legacy component with real cross-provider failover logic (AUDIT_03 §1: "TTSManager routes Uplift/Google/ElevenLabs with timeout failover and a 60s circuit breaker"). UCVE generalizes this into a single `FailoverRouter` usable for STT, LLM, and TTS alike — closing the gap AUDIT_05 §1 matrix flags ("STT/LLM retry: ABSENT" in v3 and multilingual both).

```python
class ProviderHealthState(BaseModel):
    provider_id: str
    consecutive_failures: int = 0
    circuit_open_until: float | None = None   # unix timestamp
    last_latency_ms: float | None = None


class FailoverRouter:
    """One instance per (category, language). Wraps N provider adapters in
    a priority order and applies:
      1. Per-call timeout (provider-specific, e.g. v3's TTS connect=3s/read=8s,
         AUDIT_01 §2 TTS)
      2. Retry with backoff within the SAME provider up to max_retries
         (v3 TTS pattern: 429 uses Retry-After or 1.5s; 5xx exponential
         0.5*2**(attempt-1), AUDIT_01 §2 TTS)
      3. Circuit breaker: after N consecutive failures, mark provider
         unavailable for a cooldown window (multilingual's 60s breaker,
         AUDIT_03 §1) and route to the next provider in priority order
      4. Latency-based auto-routing: if a provider's rolling p50 latency
         exceeds the budget in File 1 §4, demote its priority even if it
         hasn't hard-failed — this is `[NEW]`, no legacy repo does
         latency-based (as opposed to error-based) routing
    """

    async def call_with_failover(
        self, category: str, language: str, invoke_fn: "Callable"
    ) -> "Any": ...
```

### 5.2 Configuration-driven fallback chain (example)

```yaml
# tenant agent config excerpt — see File 8 for the full builder schema
providers:
  stt:
    ur:
      priority: [gladia]
      code_switching: false   # habiba's measured-CER decision, AUDIT_04 §2, as a default
    en:
      priority: [deepgram, gladia]  # habiba capability table pattern, AUDIT_04 §2 STT
  llm:
    default:
      priority: [groq, gemini]      # Groq first for TTFT (File 1 §4 latency budget)
  tts:
    ur:
      priority: [uplift]
    en:
      priority: [cartesia, elevenlabs, rime]   # habiba's en capability set, AUDIT_04 §2 TTS
  s2s:
    enabled: false   # opt-in per tenant; falls back to cascaded pipeline
```

---

## 6. Anti-Patterns Rejected

1. **Hardcoded temperature/max_tokens as module constants.** v3 hardcodes `temperature=0.7` and `max_output_tokens=1000` directly in `gemini_service.py` (AUDIT_01 §6 technical debt table). These are `LLMConfig` fields now, tenant-overridable via the builder schema (File 8).
2. **API keys embedded in request URLs.** Multilingual's Google TTS service builds its endpoint URL with the key as a query parameter (AUDIT_03 §5 cited `google_service.py:16`; live request is `:75`; `:16` is unused). All provider adapters in UCVE authenticate via headers set at request time, sourced from the secrets layer (File 9 roadmap, infra section), never baked into a URL string.
3. **Capability/adapter mismatch left unreconciled.** Habiba's own capability table still lists a deprecated model (`gemini-2.5-flash`) that the adapter code silently remaps to a different default (AUDIT_04 §6: "Capability table still lists `gemini-2.5-flash` as ur/en default model — mismatch with adapter remap"). UCVE's registry validates at startup that every capability-table entry resolves to a real, currently-valid adapter configuration, and fails loudly on mismatch rather than silently remapping.
