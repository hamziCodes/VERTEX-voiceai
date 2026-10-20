"""Provider factory + TTS adapter smoke tests (no network)."""

from __future__ import annotations

import os

import pytest

from core.providers.adapters.cartesia_tts import CartesiaTTSProvider
from core.providers.adapters.elevenlabs_tts import ElevenLabsTTSProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider
from core.providers.exceptions import UnknownProviderError
from core.providers.factory import (
    build_tts_provider,
    normalize_tts_provider,
)
from core.providers.interfaces.tts import TTSConfig


def test_normalize_tts_provider_defaults_and_allows_vendors() -> None:
    assert normalize_tts_provider(None) == "uplift"
    assert normalize_tts_provider("ELEVENLABS") == "elevenlabs"
    assert normalize_tts_provider("cartesia") == "cartesia"
    with pytest.raises(UnknownProviderError):
        normalize_tts_provider("nope")


def test_build_tts_provider_switches() -> None:
    assert isinstance(build_tts_provider("uplift"), UpliftTTSProvider)
    assert isinstance(build_tts_provider("elevenlabs"), ElevenLabsTTSProvider)
    assert isinstance(build_tts_provider("cartesia"), CartesiaTTSProvider)


@pytest.mark.asyncio
async def test_elevenlabs_mock_stream_without_live_flag() -> None:
    os.environ.pop("RUN_LIVE_PROVIDERS", None)
    provider = ElevenLabsTTSProvider(api_key="")
    chunks = []
    async for chunk in provider.synthesize_stream(
        "Hello there", TTSConfig(voice_id="default", sample_rate=16000)
    ):
        chunks.append(chunk)
    assert chunks
    assert sum(len(c.pcm_data) for c in chunks) > 0


@pytest.mark.asyncio
async def test_cartesia_mock_stream_without_live_flag() -> None:
    os.environ.pop("RUN_LIVE_PROVIDERS", None)
    provider = CartesiaTTSProvider(api_key="")
    chunks = []
    async for chunk in provider.synthesize_stream(
        "Hello there", TTSConfig(voice_id="default", sample_rate=16000)
    ):
        chunks.append(chunk)
    assert chunks
    assert sum(len(c.pcm_data) for c in chunks) > 0
