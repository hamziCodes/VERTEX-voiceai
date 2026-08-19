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
