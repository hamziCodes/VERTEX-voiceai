"""Provider credentials must enter adapters only through explicit injection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from core.providers.adapters.cartesia_tts import CartesiaTTSProvider
from core.providers.adapters.deepgram_stt import DeepgramSTTProvider
from core.providers.adapters.elevenlabs_tts import ElevenLabsTTSProvider
from core.providers.adapters.gemini_llm import GeminiLLMProvider
from core.providers.adapters.gladia_live_stt import GladiaLiveSTTSession
from core.providers.adapters.gladia_stt import GladiaSTTProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.openai_llm import OpenAILLMProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider
from core.providers.factory import (
    build_llm_provider,
    build_stt_provider,
    build_tts_provider,
)
from core.providers.live_stt_factory import build_live_stt_session

AdapterFactory = Callable[[str | None], Any]


@pytest.mark.parametrize(
    ("environment_names", "adapter_factory"),
    [
        (("PLATFORM_GLADIA_API_KEY", "GLADIA_API_KEY"), GladiaSTTProvider),
        (("PLATFORM_GLADIA_API_KEY", "GLADIA_API_KEY"), GladiaLiveSTTSession),
        (("PLATFORM_DEEPGRAM_API_KEY", "DEEPGRAM_API_KEY"), DeepgramSTTProvider),
        (("PLATFORM_GROQ_API_KEY", "GROQ_API_KEY"), GroqLLMProvider),
        (("GEMINI_API_KEY", "GOOGLE_API_KEY"), GeminiLLMProvider),
        (("PLATFORM_OPENAI_API_KEY", "OPENAI_API_KEY"), OpenAILLMProvider),
        (("PLATFORM_UPLIFT_API_KEY", "UPLIFT_API_KEY"), UpliftTTSProvider),
        (("PLATFORM_CARTESIA_API_KEY", "CARTESIA_API_KEY"), CartesiaTTSProvider),
        (
            (
                "PLATFORM_ELEVENLABS_API_KEY",
                "ELEVENLABS_API_KEY",
                "ELEVEN_API_KEY",
            ),
            ElevenLabsTTSProvider,
        ),
    ],
)
def test_adapter_never_reads_provider_key_environment(
    monkeypatch: pytest.MonkeyPatch,
    environment_names: tuple[str, ...],
    adapter_factory: AdapterFactory,
) -> None:
    for name in environment_names:
        monkeypatch.setenv(name, "sentinel-environment-secret")

    assert adapter_factory(None).api_key == ""
    assert adapter_factory(" explicitly-injected ").api_key == "explicitly-injected"


def test_factories_inject_exact_key_model_and_distinct_instances() -> None:
    primary_stt = build_stt_provider("deepgram", api_key="stt-primary", model="nova-3")
    fallback_stt = build_stt_provider(
        "gladia", api_key="stt-fallback", model="solaria-1"
    )
    assert primary_stt.api_key == "stt-primary"
    assert primary_stt.model == "nova-3"
    assert fallback_stt.api_key == "stt-fallback"
    assert primary_stt is not fallback_stt

    primary_llm = build_llm_provider(
        "groq", api_key="llm-primary", model="openai/gpt-oss-120b"
    )
    fallback_llm = build_llm_provider(
        "gemini", api_key="llm-fallback", model="gemini-2.5-flash"
    )
    assert primary_llm.api_key == "llm-primary"
    assert fallback_llm.api_key == "llm-fallback"
    assert primary_llm is not fallback_llm

    primary_tts = build_tts_provider("cartesia", api_key="tts-primary", model="sonic-2")
    fallback_tts = build_tts_provider(
        "elevenlabs", api_key="tts-fallback", model="eleven_flash_v2_5"
    )
    assert primary_tts.api_key == "tts-primary"
    assert primary_tts._model == "sonic-2"
    assert fallback_tts.api_key == "tts-fallback"
    assert fallback_tts._model == "eleven_flash_v2_5"
    assert primary_tts is not fallback_tts


def test_live_stt_factory_injects_exact_key_and_model() -> None:
    session = build_live_stt_session(
        "gladia",
        api_key="live-stt-key",
        model="solaria-1",
        language="ur",
        endpointing=0.25,
        receive_partials=True,
    )
    assert session is not None
    assert session.api_key == "live-stt-key"
    assert session._model == "solaria-1"
