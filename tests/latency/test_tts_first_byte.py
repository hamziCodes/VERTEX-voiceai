from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
import pytest

from core.providers.adapters.uplift_tts import UpliftTTSProvider
from core.providers.interfaces.llm import LLMConfig, LLMStreamChunk
from core.providers.interfaces.tts import (
    BaseTTSProvider,
    TTSChunk,
    TTSConfig,
    TTSStreamTimeoutError,
    TTSStreamTimeouts,
    iterate_tts_stream,
)
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


@pytest.mark.asyncio
async def test_uplift_yields_network_bytes_before_response_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "1")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "0")
    release_tail = asyncio.Event()

    class DelayedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"\x01\x00" * 40
            await release_tail.wait()
            yield b"\x02\x00" * 160

    provider = UpliftTTSProvider(api_key="test-key", chunk_size_bytes=320)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=DelayedStream())
        )
    )
    stream = provider.synthesize_stream(
        "hello", TTSConfig(voice_id="test", sample_rate=16000)
    )

    first = await asyncio.wait_for(anext(stream), timeout=0.2)
    assert first.pcm_data == b"\x01\x00" * 40
    release_tail.set()
    remaining = [chunk async for chunk in stream]
    assert b"".join(chunk.pcm_data for chunk in remaining) == b"\x02\x00" * 160
    await provider.aclose()


@pytest.mark.asyncio
async def test_tts_deadlines_distinguish_first_chunk_and_inter_chunk_idle() -> None:
    async def slow_first():
        await asyncio.sleep(0.03)
        yield object()

    with pytest.raises(TTSStreamTimeoutError, match="first_chunk"):
        _ = [
            item
            async for item in iterate_tts_stream(
                slow_first(),
                TTSStreamTimeouts(
                    first_chunk_seconds=0.005, idle_seconds=0.1, overall_seconds=0.2
                ),
            )
        ]

    async def slow_middle():
        yield object()
        await asyncio.sleep(0.03)
        yield object()

    with pytest.raises(TTSStreamTimeoutError, match="inter_chunk_idle"):
        _ = [
            item
            async for item in iterate_tts_stream(
                slow_middle(),
                TTSStreamTimeouts(
                    first_chunk_seconds=0.1, idle_seconds=0.005, overall_seconds=0.2
                ),
            )
        ]

    async def exceeds_overall():
        for _ in range(10):
            await asyncio.sleep(0.01)
            yield object()

    with pytest.raises(TTSStreamTimeoutError, match="overall"):
        _ = [
            item
            async for item in iterate_tts_stream(
                exceeds_overall(),
                TTSStreamTimeouts(
                    first_chunk_seconds=0.1,
                    idle_seconds=0.1,
                    overall_seconds=0.025,
                ),
            )
        ]


@pytest.mark.asyncio
async def test_pipeline_emits_first_audio_before_llm_stream_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    release_llm = asyncio.Event()
    first_audio = asyncio.Event()

    class PausedLLM:
        def health_check(self) -> bool:
            return True

        async def generate_stream(
            self, messages, config: LLMConfig, cancellation_token=None
        ):
            yield LLMStreamChunk(text="One two three ", is_first_token=True)
            await release_llm.wait()
            yield LLMStreamChunk(text="four five.", finish_reason="stop")

    class ImmediateTTS(BaseTTSProvider):
        def health_check(self) -> bool:
            return True

        async def synthesize_stream(self, text, config, cancellation_token=None):
            yield TTSChunk(b"\x01\x00" * 160, native_sample_rate=16000, is_final=True)

    orchestrator = PipelineOrchestrator(on_audio_out=lambda _: first_audio.set())
    orchestrator.llm_provider = PausedLLM()
    orchestrator.tts_provider = ImmediateTTS()
    config = PipelineSessionConfig(
        session_id="phase-03-streaming",
        tenant_id="tenant",
        agent_id="agent",
        language="en",
    )

    turn = asyncio.create_task(orchestrator.run_turn(config, "hello"))
    await asyncio.wait_for(first_audio.wait(), timeout=0.5)
    assert turn.done() is False
    release_llm.set()
    assert await asyncio.wait_for(turn, timeout=1.0) == "One two three four five."
    await orchestrator.finalize_session(config)


@pytest.mark.asyncio
async def test_partial_tts_failure_does_not_replay_or_append_mock_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    audio: list[bytes] = []

    class PartialFailureTTS(BaseTTSProvider):
        def health_check(self) -> bool:
            return True

        async def synthesize_stream(self, text, config, cancellation_token=None):
            yield TTSChunk(b"\x01\x00" * 160, native_sample_rate=16000)
            raise RuntimeError("stream disconnected")

    orchestrator = PipelineOrchestrator(on_audio_out=audio.append)
    orchestrator.tts_provider = PartialFailureTTS()
    config = PipelineSessionConfig(
        session_id="phase-03-partial",
        tenant_id="tenant",
        agent_id="agent",
    )
    waterfall = orchestrator.latency_hooks.start_turn(uuid4())

    await orchestrator._synthesize_streaming(["hello"], config, waterfall)
    await asyncio.sleep(0)

    assert audio == [b"\x01\x00" * 160]
    await orchestrator.finalize_session(config)


@pytest.mark.asyncio
async def test_multiple_speech_chunks_are_synthesized_after_audio_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    spoken: list[str] = []

    class RecordingTTS(BaseTTSProvider):
        def health_check(self) -> bool:
            return True

        async def synthesize_stream(self, text, config, cancellation_token=None):
            spoken.append(text)
            yield TTSChunk(b"\x01\x00" * 80, native_sample_rate=16000, is_final=True)

    orchestrator = PipelineOrchestrator(on_audio_out=lambda _: None)
    orchestrator.tts_provider = RecordingTTS()
    config = PipelineSessionConfig(
        session_id="phase-03-multiple",
        tenant_id="tenant",
        agent_id="agent",
    )
    waterfall = orchestrator.latency_hooks.start_turn(uuid4())

    await orchestrator._synthesize_streaming(["one", "two"], config, waterfall)

    assert spoken == ["one", "two"]
    await orchestrator.finalize_session(config)


@pytest.mark.asyncio
async def test_empty_tts_stream_does_not_emit_fake_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    audio: list[bytes] = []

    class EmptyTTS(BaseTTSProvider):
        def health_check(self) -> bool:
            return True

        async def synthesize_stream(self, text, config, cancellation_token=None):
            if False:
                yield TTSChunk(b"")

    orchestrator = PipelineOrchestrator(on_audio_out=audio.append)
    orchestrator.tts_provider = EmptyTTS()
    config = PipelineSessionConfig(
        session_id="phase-03-empty",
        tenant_id="tenant",
        agent_id="agent",
    )
    waterfall = orchestrator.latency_hooks.start_turn(uuid4())

    await orchestrator._synthesize_streaming(["hello"], config, waterfall)
    await asyncio.sleep(0)

    assert audio == []
    await orchestrator.finalize_session(config)


@pytest.mark.asyncio
async def test_uplift_parses_split_wave_header_without_emitting_container_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "1")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "0")
    pcm = b"\x34\x12" * 160
    header = (
        b"RIFF"
        + (48 + len(pcm)).to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (16000).to_bytes(4, "little")
        + (32000).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"JUNK"
        + (3).to_bytes(4, "little")
        + b"abc\x00"
        + b"data"
        + len(pcm).to_bytes(4, "little")
    )

    class SplitWave(httpx.AsyncByteStream):
        async def __aiter__(self):
            blob = header + pcm
            start = 0
            for end in (5, 19, 41, len(blob)):
                yield blob[start:end]
                start = end

    provider = UpliftTTSProvider(api_key="test-key", chunk_size_bytes=320)
    provider._output_format = "WAV_16000_16"
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=SplitWave())
        )
    )
    chunks = [
        chunk
        async for chunk in provider.synthesize_stream(
            "hello", TTSConfig(voice_id="test", sample_rate=16000)
        )
    ]

    assert b"".join(chunk.pcm_data for chunk in chunks) == pcm
    await provider.aclose()
