from __future__ import annotations

import pytest

from core.providers.adapters.cartesia_tts import CartesiaTTSProvider
from core.providers.adapters.deepgram_stt import DeepgramSTTProvider
from core.providers.adapters.elevenlabs_tts import ElevenLabsTTSProvider
from core.providers.adapters.gemini_llm import GeminiLLMProvider
from core.providers.adapters.gladia_stt import GladiaSTTProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.openai_llm import OpenAILLMProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider

PROVIDER_TYPES = (
    GladiaSTTProvider,
    DeepgramSTTProvider,
    GroqLLMProvider,
    GeminiLLMProvider,
    OpenAILLMProvider,
    UpliftTTSProvider,
    CartesiaTTSProvider,
    ElevenLabsTTSProvider,
)


@pytest.mark.parametrize("provider_type", PROVIDER_TYPES)
def test_health_check_reports_mock_or_credential_readiness(
    monkeypatch: pytest.MonkeyPatch,
    provider_type: type,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    assert provider_type(api_key="").health_check() is True

    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "0")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "1")
    assert provider_type(api_key="").health_check() is False
    assert provider_type(api_key="test").health_check() is True
