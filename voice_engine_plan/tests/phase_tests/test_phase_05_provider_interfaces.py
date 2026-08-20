"""Phase 05: Provider Interface Contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def interfaces_module():
    try:
        from core.providers import interfaces  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 05 implementation pending: {exc}")
    return interfaces


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_05_provider_interface_contracts.md"
    )
    assert plan.is_file()


def test_null_stt_health_check(interfaces_module) -> None:
    from core.providers.adapters.null_stt import NullSTTProvider  # type: ignore

    provider = NullSTTProvider()
    assert provider.health_check() is not None


@pytest.mark.asyncio
async def test_tts_honors_cancel_token(interfaces_module) -> None:
    from core.buffers.cancellation import AsyncioCancellationToken  # type: ignore
    from core.providers.adapters.null_tts import NullTTSProvider  # type: ignore
    from core.providers.interfaces.tts import TTSConfig  # type: ignore

    provider = NullTTSProvider()
    token = AsyncioCancellationToken()
    token.cancel()
    chunks = []
    async for chunk in provider.synthesize_stream("hi", TTSConfig(voice_id="test"), token):
        chunks.append(chunk)
    assert chunks == []


def test_abc_cannot_be_instantiated(interfaces_module) -> None:
    from core.providers.interfaces.llm import BaseLLMProvider  # type: ignore
    from core.providers.interfaces.s2s import BaseSpeechToSpeechProvider  # type: ignore
    from core.providers.interfaces.stt import BaseSTTProvider  # type: ignore
    from core.providers.interfaces.tts import BaseTTSProvider  # type: ignore
    from core.providers.interfaces.vad import BaseVADProvider  # type: ignore

    for abc_cls in (
        BaseVADProvider,
        BaseSTTProvider,
        BaseLLMProvider,
        BaseTTSProvider,
        BaseSpeechToSpeechProvider,
    ):
        with pytest.raises(TypeError):
            abc_cls()  # type: ignore


def test_all_null_adapters_health_check(interfaces_module) -> None:
    from core.providers.adapters.null_llm import NullLLMProvider  # type: ignore
    from core.providers.adapters.null_s2s import NullS2SProvider  # type: ignore
    from core.providers.adapters.null_stt import NullSTTProvider  # type: ignore
    from core.providers.adapters.null_tts import NullTTSProvider  # type: ignore
    from core.providers.adapters.null_vad import NullVADProvider  # type: ignore

    assert NullVADProvider().health_check() is True
    assert NullSTTProvider().health_check() is True
    assert NullLLMProvider().health_check() is True
    assert NullTTSProvider().health_check() is True
    assert NullS2SProvider().health_check() is True


def test_stt_config_validation_rejects_empty_language(interfaces_module) -> None:
    from core.providers.interfaces.stt import STTConfig  # type: ignore

    with pytest.raises(ValueError):
        STTConfig(language="")

