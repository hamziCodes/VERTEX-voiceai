"""UCVE Null & Concrete Provider Adapters Package."""

from __future__ import annotations

from core.providers.adapters.null_llm import NullLLMProvider
from core.providers.adapters.null_s2s import NullS2SProvider
from core.providers.adapters.null_stt import NullSTTProvider
from core.providers.adapters.null_tts import NullTTSProvider
from core.providers.adapters.null_vad import NullVADProvider

__all__ = [
    "NullVADProvider",
    "NullSTTProvider",
    "NullLLMProvider",
    "NullTTSProvider",
    "NullS2SProvider",
]
