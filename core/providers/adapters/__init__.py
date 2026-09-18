"""UCVE Null & Concrete Provider Adapters Package."""

from __future__ import annotations

from core.providers.adapters.cartesia_tts import CartesiaTTSProvider
from core.providers.adapters.deepgram_stt import DeepgramSTTProvider
from core.providers.adapters.elevenlabs_tts import ElevenLabsTTSProvider
from core.providers.adapters.gemini_llm import GeminiLLMProvider
from core.providers.adapters.gladia_stt import GladiaSTTProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.null_llm import NullLLMProvider
from core.providers.adapters.null_s2s import NullS2SProvider
from core.providers.adapters.null_stt import NullSTTProvider
from core.providers.adapters.null_tts import NullTTSProvider
from core.providers.adapters.null_vad import NullVADProvider
from core.providers.adapters.openai_llm import OpenAILLMProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider

__all__ = [
    "NullVADProvider",
    "NullSTTProvider",
    "NullLLMProvider",
    "NullTTSProvider",
    "NullS2SProvider",
    "GladiaSTTProvider",
    "DeepgramSTTProvider",
    "GroqLLMProvider",
    "GeminiLLMProvider",
    "OpenAILLMProvider",
    "UpliftTTSProvider",
    "ElevenLabsTTSProvider",
    "CartesiaTTSProvider",
]

