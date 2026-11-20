from __future__ import annotations

import asyncio
import base64
import math
import struct
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.llm import BaseLLMProvider, LLMConfig, LLMStreamChunk
from core.providers.interfaces.stt import BaseSTTProvider, STTConfig, Transcript
from core.providers.interfaces.tts import BaseTTSProvider, TTSChunk, TTSConfig
from core.providers.interfaces.vad import VADEvent
from core.providers.routing import ProviderRouteIdentity, ResolvedProviderRoute
from core.runtime.session_plan import RuntimeProviderRoute
from core.types.audio import AudioFrame
from telephony_gateway.transcoding.mulaw import pcm16_to_mulaw
from tests.telephony.fake_telnyx import FakeTelnyxSocket
from worker_raw.orchestration.session_config import PipelineSessionConfig

STREAM_URL = "wss://voice.example.test/v1/telnyx/media?token=phase12d-fixture"
CALL_CONTROL_ID = "v3:phase12d-call"
STREAM_ID = "6ab7c934-c85d-4f8d-85ea-a6e5d4bf47c1"
NOW = 1_793_181_600


def signed_media_headers() -> tuple[str, str, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key = base64.b64encode(private_key.public_key().public_bytes_raw()).decode()
    signature = base64.b64encode(
        private_key.sign(f"{NOW}|{STREAM_URL}".encode())
    ).decode()
    return public_key, signature, str(NOW)


def connected() -> dict[str, object]:
    return {"event": "connected", "version": "1.0.0"}


def start() -> dict[str, object]:
    return {
        "event": "start",
        "sequence_number": "1",
        "stream_id": STREAM_ID,
        "start": {
            "call_control_id": CALL_CONTROL_ID,
            "call_session_id": "phase12d-carrier-session",
            "media_format": {"encoding": "PCMU", "sample_rate": 8000, "channels": 1},
        },
    }


def media(chunk: int, *, speech: bool = True) -> dict[str, object]:
    samples = [
        int(9000 * math.sin(2 * math.pi * 440 * index / 8000)) if speech else 0
        for index in range(160)
    ]
    pcm = struct.pack("<160h", *samples)
    return {
        "event": "media",
        "sequence_number": str(chunk + 1),
        "stream_id": STREAM_ID,
        "media": {
            "track": "inbound",
            "chunk": str(chunk),
            "timestamp": str(chunk * 20),
            "payload": base64.b64encode(pcm16_to_mulaw(pcm)).decode(),
        },
    }


def stop() -> dict[str, object]:
    return {
        "event": "stop",
        "sequence_number": "99",
        "stream_id": STREAM_ID,
        "stop": {"call_control_id": CALL_CONTROL_ID},
    }


class ScriptedVAD:
    def __init__(self, events: list[VADEvent]) -> None:
        self.events = events
        self.index = 0
        self.is_speaking = False

    def health_check(self) -> bool:
        return True

    def reset(self) -> None:
        self.index = 0
        self.is_speaking = False

    def configure(self, **_kwargs: object) -> None:
        return None

    def process_frame(self, _frame: AudioFrame) -> VADEvent:
        event = (
            self.events[self.index]
            if self.index < len(self.events)
            else VADEvent(False, False, 0.0)
        )
        self.index += 1
        if event.speech_start:
            self.is_speaking = True
        if event.speech_end:
            self.is_speaking = False
        return event


class SequenceSTT(BaseSTTProvider):
    provider_id = "fake-stt"
    provider_mode = "test"

    def __init__(self, texts: list[str]) -> None:
        self.texts = texts
        self.calls = 0
        self.audio_bytes = 0
        self.closed = False

    def health_check(self) -> bool:
        return True

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        config: STTConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[Transcript]:
        del cancellation_token
        async for frame in audio_stream:
            self.audio_bytes += len(frame.pcm16)
        text = self.texts[min(self.calls, len(self.texts) - 1)]
        self.calls += 1
        yield Transcript(
            text=text, is_final=True, confidence=1.0, language=config.language
        )

    async def aclose(self) -> None:
        self.closed = True


class SequenceLLM(BaseLLMProvider):
    provider_id = "fake-llm"
    provider_mode = "test"

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls = 0
        self.messages: list[list[dict[str, Any]]] = []
        self.closed = False

    def health_check(self) -> bool:
        return True

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        config: LLMConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        del config
        self.messages.append(messages)
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        if cancellation_token is None or not cancellation_token.is_cancelled:
            yield LLMStreamChunk(text=reply, is_first_token=True, finish_reason="stop")

    async def aclose(self) -> None:
        self.closed = True


class SequenceTTS(BaseTTSProvider):
    provider_id = "fake-tts"
    provider_mode = "test"

    def __init__(
        self, *, chunks_per_call: int = 2, block_between: bool = False
    ) -> None:
        self.chunks_per_call = chunks_per_call
        self.block_between = block_between
        self.calls = 0
        self.chunks_yielded = 0
        self.release = asyncio.Event()
        self.closed = False

    def health_check(self) -> bool:
        return True

    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[TTSChunk]:
        del text
        self.calls += 1
        for index in range(self.chunks_per_call):
            if cancellation_token is not None and cancellation_token.is_cancelled:
                return
            self.chunks_yielded += 1
            yield TTSChunk(
                pcm_data=struct.pack("<320h", *([4000] * 320)),
                native_sample_rate=config.sample_rate,
                is_final=index == self.chunks_per_call - 1,
            )
            if self.block_between and index == 0:
                await self.release.wait()

    async def aclose(self) -> None:
        self.closed = True
        self.release.set()


@dataclass
class FakeProviderStack:
    stt: SequenceSTT
    llm: SequenceLLM
    tts: SequenceTTS

    def build_chain(
        self,
        tenant_id: str,
        category: str,
        language: str,
        routes: tuple[RuntimeProviderRoute, ...],
    ) -> tuple[ResolvedProviderRoute, ...]:
        del language
        adapter = {"stt": self.stt, "llm": self.llm, "tts": self.tts}[category]
        return tuple(
            ResolvedProviderRoute(
                identity=ProviderRouteIdentity(
                    category=category,
                    provider_id=route.provider_id,
                    model=route.model,
                    region="local_test",
                    tenant_id=tenant_id,
                    credential_scope="sanitized-test-scope",
                ),
                adapter=adapter,
            )
            for route in routes
        )


def authoritative_config(
    *, session_id: str, tenant_id: str, agent_id: str
) -> PipelineSessionConfig:
    def routes(category: str) -> list[dict[str, object]]:
        return [
            RuntimeProviderRoute(
                provider_id=f"fake-{category}-primary", priority=1
            ).model_dump(mode="json"),
            RuntimeProviderRoute(
                provider_id=f"fake-{category}-fallback", priority=2
            ).model_dump(mode="json"),
        ]

    return PipelineSessionConfig(
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        transport_type="telephony",
        plan_authoritative=True,
        session_plan_ref="phase12d-plan",
        session_plan_hash="phase12d-plan-hash",
        agent_config_version=1,
        provider_chain={
            category: routes(category) for category in ("stt", "llm", "tts")
        },
        tts_voice_id="fake-voice",
    )


def sent_events(socket: FakeTelnyxSocket, event: str) -> list[dict[str, Any]]:
    return [payload for _at, payload in socket.sent if payload.get("event") == event]


def decoded_media_payloads(socket: FakeTelnyxSocket) -> list[bytes]:
    return [
        base64.b64decode(item["media"]["payload"])
        for item in sent_events(socket, "media")
    ]
