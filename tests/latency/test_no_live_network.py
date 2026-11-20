from __future__ import annotations

import socket

import pytest

from core.providers.adapters.cartesia_tts import CartesiaTTSProvider
from core.providers.adapters.deepgram_stt import DeepgramSTTProvider
from core.providers.adapters.elevenlabs_tts import ElevenLabsTTSProvider
from core.providers.adapters.gemini_llm import GeminiLLMProvider
from core.providers.adapters.gladia_stt import GladiaSTTProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.openai_llm import OpenAILLMProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider
from core.providers.exceptions import ConfigurationError
from core.providers.interfaces.llm import LLMConfig
from core.providers.interfaces.stt import STTConfig
from core.providers.interfaces.tts import TTSConfig
from core.types.audio import AudioFrame
from tests.latency.network_guard import OutboundNetworkError, deny_outbound_network


def test_network_guard_blocks_external_dns_but_allows_loopback_resolution() -> None:
    with deny_outbound_network():
        with pytest.raises(OutboundNetworkError, match="example.com"):
            socket.getaddrinfo("example.com", 443)
        assert socket.getaddrinfo("127.0.0.1", 8080)


@pytest.mark.asyncio
async def test_offline_scripted_baseline_makes_no_network_attempts(tmp_path) -> None:
    from tests.latency.baseline import run_baseline

    with deny_outbound_network() as attempts:
        report, _ = await run_baseline(
            output_dir=tmp_path,
            repetitions=1,
            fixture_ids=("short-en",),
            commit="abc123",
        )

    assert report.sample_count == 1
    assert attempts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "provider_id"),
    (
        ("stt", "gladia"),
        ("stt", "deepgram"),
        ("llm", "groq"),
        ("llm", "gemini"),
        ("llm", "openai"),
        ("tts", "uplift"),
        ("tts", "cartesia"),
        ("tts", "elevenlabs"),
    ),
)
async def test_production_mode_missing_credentials_never_returns_fake_success(
    monkeypatch: pytest.MonkeyPatch, kind: str, provider_id: str
) -> None:
    for name in (
        "GLADIA_API_KEY",
        "GROQ_API_KEY",
        "UPLIFT_API_KEY",
        "DEEPGRAM_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "CARTESIA_API_KEY",
        "ELEVENLABS_API_KEY",
        "ELEVEN_API_KEY",
        "PLATFORM_GLADIA_API_KEY",
        "PLATFORM_GROQ_API_KEY",
        "PLATFORM_UPLIFT_API_KEY",
        "PLATFORM_DEEPGRAM_API_KEY",
        "PLATFORM_GEMINI_API_KEY",
        "PLATFORM_OPENAI_API_KEY",
        "PLATFORM_CARTESIA_API_KEY",
        "PLATFORM_ELEVENLABS_API_KEY",
        "RUN_LIVE_PROVIDERS",
        "RUN_MOCK_PROVIDERS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UCVE_ENV", "production")

    async def audio_stream():
        yield AudioFrame(pcm16=b"\x00\x00" * 1600)

    with pytest.raises(ConfigurationError, match="credential"):
        if kind == "stt":
            provider = (
                GladiaSTTProvider(api_key="", mock_text="fake")
                if provider_id == "gladia"
                else DeepgramSTTProvider(api_key="", mock_text="fake")
            )
            stream = provider.transcribe_stream(audio_stream(), STTConfig())
        elif kind == "llm":
            llm_types = {
                "groq": GroqLLMProvider,
                "gemini": GeminiLLMProvider,
                "openai": OpenAILLMProvider,
            }
            stream = llm_types[provider_id](api_key="").generate_stream(
                [{"role": "user", "content": "hello"}], LLMConfig(model="test")
            )
        else:
            tts_types = {
                "uplift": UpliftTTSProvider,
                "cartesia": CartesiaTTSProvider,
                "elevenlabs": ElevenLabsTTSProvider,
            }
            stream = tts_types[provider_id](api_key="").synthesize_stream(
                "hello", TTSConfig(voice_id="test")
            )
        await anext(stream)
