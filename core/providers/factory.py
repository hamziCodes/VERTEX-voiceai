"""Factory helpers for swapping concrete STT/LLM/TTS adapters."""

from __future__ import annotations

from core.listening.config import SpeakingPipelineConfig
from core.providers.adapters.cartesia_tts import CartesiaTTSProvider
from core.providers.adapters.deepgram_stt import DeepgramSTTProvider
from core.providers.adapters.elevenlabs_tts import ElevenLabsTTSProvider
from core.providers.adapters.gemini_llm import GeminiLLMProvider
from core.providers.adapters.gladia_stt import GladiaSTTProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.openai_llm import OpenAILLMProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider
from core.providers.interfaces.llm import BaseLLMProvider
from core.providers.interfaces.stt import BaseSTTProvider
from core.providers.interfaces.tts import BaseTTSProvider
from core.providers.spec import (
    DEFAULT_PROVIDER_CATALOG,
    ProviderCategory,
    get_provider_spec,
)

SUPPORTED_STT = frozenset(
    spec.provider_id
    for spec in DEFAULT_PROVIDER_CATALOG.by_category(ProviderCategory.STT)
)
SUPPORTED_LLM = frozenset(
    spec.provider_id
    for spec in DEFAULT_PROVIDER_CATALOG.by_category(ProviderCategory.LLM)
)
SUPPORTED_TTS = frozenset(
    spec.provider_id
    for spec in DEFAULT_PROVIDER_CATALOG.by_category(ProviderCategory.TTS)
)


def normalize_stt_provider(provider_id: str | None) -> str:
    pid = (provider_id or "gladia").strip().lower()
    return get_provider_spec(pid, category=ProviderCategory.STT).provider_id


def normalize_llm_provider(provider_id: str | None) -> str:
    pid = (provider_id or "groq").strip().lower()
    return get_provider_spec(pid, category=ProviderCategory.LLM).provider_id


def normalize_tts_provider(provider_id: str | None) -> str:
    pid = (provider_id or "uplift").strip().lower()
    return get_provider_spec(pid, category=ProviderCategory.TTS).provider_id


def build_stt_provider(
    provider_id: str | None,
    *,
    api_key: str | None,
    model: str | None = None,
    mock_text: str = "",
) -> BaseSTTProvider:
    pid = normalize_stt_provider(provider_id)
    if pid == "deepgram":
        return DeepgramSTTProvider(
            api_key=api_key,
            model=model or "nova-3",
            mock_text=mock_text,
        )
    return GladiaSTTProvider(api_key=api_key, mock_text=mock_text)


def build_llm_provider(
    provider_id: str | None,
    *,
    api_key: str | None,
    model: str | None = None,
) -> BaseLLMProvider:
    pid = normalize_llm_provider(provider_id)
    if pid == "gemini":
        return GeminiLLMProvider(api_key=api_key, model=model)
    if pid == "openai":
        return OpenAILLMProvider(api_key=api_key, model=model)
    return GroqLLMProvider(api_key=api_key, model=model)


def build_tts_provider(
    provider_id: str | None,
    *,
    api_key: str | None,
    model: str | None = None,
    speaking_config: SpeakingPipelineConfig | None = None,
) -> BaseTTSProvider:
    pid = normalize_tts_provider(provider_id)
    chunk = 3200
    if speaking_config is not None and speaking_config.enable_speaking_hardening:
        chunk = speaking_config.tts_chunk_size_bytes
    if pid == "elevenlabs":
        return ElevenLabsTTSProvider(
            api_key=api_key, model=model, chunk_size_bytes=chunk
        )
    if pid == "cartesia":
        return CartesiaTTSProvider(api_key=api_key, model=model, chunk_size_bytes=chunk)
    return UpliftTTSProvider(api_key=api_key, chunk_size_bytes=chunk)
