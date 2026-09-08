"""Factory helpers for swapping concrete STT/LLM/TTS adapters."""

from __future__ import annotations

from core.listening.config import SpeakingPipelineConfig
from core.providers.adapters.cartesia_tts import CartesiaTTSProvider
from core.providers.adapters.elevenlabs_tts import ElevenLabsTTSProvider
from core.providers.adapters.gladia_stt import GladiaSTTProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider
from core.providers.interfaces.llm import BaseLLMProvider
from core.providers.interfaces.stt import BaseSTTProvider
from core.providers.interfaces.tts import BaseTTSProvider

SUPPORTED_STT = frozenset({"gladia"})
SUPPORTED_LLM = frozenset({"groq"})
SUPPORTED_TTS = frozenset({"uplift", "elevenlabs", "cartesia"})


def normalize_stt_provider(provider_id: str | None) -> str:
    pid = (provider_id or "gladia").strip().lower()
    return pid if pid in SUPPORTED_STT else "gladia"


def normalize_llm_provider(provider_id: str | None) -> str:
    pid = (provider_id or "groq").strip().lower()
    return pid if pid in SUPPORTED_LLM else "groq"


def normalize_tts_provider(provider_id: str | None) -> str:
    pid = (provider_id or "uplift").strip().lower()
    return pid if pid in SUPPORTED_TTS else "uplift"


def build_stt_provider(provider_id: str | None, *, mock_text: str = "") -> BaseSTTProvider:
    _ = normalize_stt_provider(provider_id)
    return GladiaSTTProvider(mock_text=mock_text)


def build_llm_provider(provider_id: str | None) -> BaseLLMProvider:
    _ = normalize_llm_provider(provider_id)
    return GroqLLMProvider()


def build_tts_provider(
    provider_id: str | None,
    *,
    speaking_config: SpeakingPipelineConfig | None = None,
) -> BaseTTSProvider:
    pid = normalize_tts_provider(provider_id)
    chunk = 3200
    if speaking_config is not None and speaking_config.enable_speaking_hardening:
        chunk = speaking_config.tts_chunk_size_bytes
    if pid == "elevenlabs":
        return ElevenLabsTTSProvider(chunk_size_bytes=chunk)
    if pid == "cartesia":
        return CartesiaTTSProvider(chunk_size_bytes=chunk)
    return UpliftTTSProvider(chunk_size_bytes=chunk)
