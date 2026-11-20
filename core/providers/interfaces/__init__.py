"""UCVE Provider Abstract Interface Contracts Package."""

from __future__ import annotations

from core.providers.interfaces.capability import (
    ProviderCapabilityEntry,
    ProviderCapabilityStatus,
)
from core.providers.interfaces.llm import (
    BaseLLMProvider,
    LLMConfig,
    LLMStreamChunk,
    ToolDefinition,
)
from core.providers.interfaces.s2s import (
    BaseSpeechToSpeechProvider,
    S2SConfig,
    S2SEvent,
)
from core.providers.interfaces.stt import (
    BaseSTTProvider,
    STTConfig,
    Transcript,
)
from core.providers.interfaces.tts import (
    BaseTTSProvider,
    TTSChunk,
    TTSConfig,
    TTSStreamTimeoutError,
    TTSStreamTimeouts,
    iterate_tts_stream,
)
from core.providers.interfaces.vad import (
    BaseVADProvider,
    VADConfig,
    VADEvent,
)

__all__ = [
    "ProviderCapabilityStatus",
    "ProviderCapabilityEntry",
    "BaseVADProvider",
    "VADConfig",
    "VADEvent",
    "BaseSTTProvider",
    "STTConfig",
    "Transcript",
    "BaseLLMProvider",
    "LLMConfig",
    "LLMStreamChunk",
    "ToolDefinition",
    "BaseTTSProvider",
    "TTSConfig",
    "TTSChunk",
    "TTSStreamTimeoutError",
    "TTSStreamTimeouts",
    "iterate_tts_stream",
    "BaseSpeechToSpeechProvider",
    "S2SConfig",
    "S2SEvent",
]
