"""UCVE Gladia Live STT — real-time WebSocket streaming session.

Implements Gladia's v2 *live* API: a REST init handshake returns a session
WebSocket URL, then audio is streamed in and partial/final transcripts stream
out on two cooperating asyncio loops. Falls back cleanly to a disabled (mock)
session when no key is configured or ``RUN_LIVE_PROVIDERS`` is not ``1`` — the
orchestrator then relies on the REST batch adapter + local VAD endpointing.

Harvested pattern: ``Multilingual_AI_Voice_Agent`` ``gladia_service.py`` init.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from core.observability.logging import get_logger
from core.providers.interfaces.live_stt import BaseLiveSTTSession
from core.providers.interfaces.stt import Transcript

logger = get_logger("ucve.providers.gladia_live")

_GLADIA_LIVE_INIT = "https://api.gladia.io/v2/live"
_STOP_SENTINEL = object()


class GladiaLiveSTTSession(BaseLiveSTTSession):
    """A single Gladia live streaming session (connect → stream → close)."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        language: str = "en",
        endpointing: float = 0.2,
        receive_partials: bool = True,
        sample_rate: int = 16000,
        model: str = "solaria-1",
        connect_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.api_key = (
            api_key
            or os.environ.get("PLATFORM_GLADIA_API_KEY")
            or os.environ.get("GLADIA_API_KEY")
            or ""
        ).strip()
        self._language = language
        self._endpointing = endpointing
        self._receive_partials = receive_partials
        self._sample_rate = sample_rate
        self._model = model
        # Injectable connect for tests (mock WS server); defaults to `websockets`.
        self._connect_factory = connect_factory

        self._ws: Any | None = None
        self._live = False
        self._audio_q: asyncio.Queue[bytes | object] = asyncio.Queue(maxsize=256)
        self._transcript_q: asyncio.Queue[Transcript | object] = asyncio.Queue(
            maxsize=256
        )
        self.dropped_partial_count = 0
        self.dropped_final_count = 0
        self._send_task: asyncio.Task[None] | None = None
        self._recv_task: asyncio.Task[None] | None = None
        self._closed = False

    @property
    def is_live(self) -> bool:
        return self._live

    @property
    def transcript_queue_capacity(self) -> int:
        return self._transcript_q.maxsize

    def _use_mock(self) -> bool:
        return (
            not self.api_key
            or os.environ.get("RUN_MOCK_PROVIDERS") == "1"
            or os.environ.get("RUN_LIVE_PROVIDERS") != "1"
        )

    async def start(self) -> bool:
        """Initialise the live session. Returns True when a live WS is active."""
        if self._use_mock():
            logger.info("Gladia Live disabled (mock/no-key) — using batch fallback.")
            self._live = False
            return False

        try:
            ws_url = await self._init_session()
            self._ws = await self._connect(ws_url)
            self._live = True
            self._send_task = asyncio.create_task(self._send_loop())
            self._recv_task = asyncio.create_task(self._recv_loop())
            logger.info("Gladia Live session connected")
            return True
        except Exception as exc:  # pragma: no cover - network failure path
            logger.error(
                "Gladia Live init failed; falling back to batch",
                error=str(exc),
            )
            self._live = False
            return False

    async def _init_session(self) -> str:
        # Match working Multilingual legacy: multi-lang + code switching so
        # English-only config does not drop code-switched / accented speech.
        languages = [self._language] if self._language else ["en"]
        for extra in ("en", "ur", "ar", "ms"):
            if extra not in languages:
                languages.append(extra)
        config = {
            "encoding": "wav/pcm",
            "sample_rate": self._sample_rate,
            "bit_depth": 16,
            "channels": 1,
            "model": self._model,
            "endpointing": self._endpointing,
            "language_config": {
                "languages": languages,
                "code_switching": True,
            },
            "messages_config": {
                "receive_partial_transcripts": self._receive_partials,
                "receive_final_transcripts": True,
                "receive_errors": True,
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _GLADIA_LIVE_INIT,
                headers={"x-gladia-key": self.api_key},
                json=config,
            )
            resp.raise_for_status()
            data = resp.json()
        url = data.get("url") or data.get("ws_url")
        if not url:
            raise RuntimeError("Gladia live init returned no WS url")
        return str(url)

    async def _connect(self, url: str) -> Any:
        if self._connect_factory is not None:
            return await self._connect_factory(url)
        import websockets  # local import; optional dependency guard

        return await websockets.connect(url, max_size=None)

    async def _send_loop(self) -> None:
        try:
            while True:
                item = await self._audio_q.get()
                if item is _STOP_SENTINEL:
                    await self._send_stop()
                    return
                assert isinstance(item, (bytes, bytearray))
                await self._ws.send(bytes(item))
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover
            logger.warning("Gladia Live send loop ended", error=str(exc))

    async def _send_stop(self) -> None:
        try:
            await self._ws.send(json.dumps({"type": "stop_recording"}))
        except Exception:  # pragma: no cover
            pass

    async def _recv_loop(self) -> None:
        try:
            async for raw in self._ws:
                transcript = self._parse_message(raw)
                if transcript is not None:
                    await self._queue_transcript(transcript)
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover
            logger.warning("Gladia Live recv loop ended", error=str(exc))
        finally:
            await self._transcript_q.put(_STOP_SENTINEL)

    async def _queue_transcript(self, transcript: Transcript) -> None:
        """Bound partials while applying lossless backpressure to finals."""
        if transcript.is_final:
            await self._transcript_q.put(transcript)
            return
        try:
            self._transcript_q.put_nowait(transcript)
        except asyncio.QueueFull:
            self.dropped_partial_count += 1

    def _parse_message(self, raw: str | bytes) -> Transcript | None:
        try:
            data = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        msg_type = data.get("type")
        if msg_type == "error":
            logger.error("Gladia Live error event", payload=data.get("data") or data)
            return None
        if msg_type != "transcript":
            return None
        payload = data.get("data", {}) or {}
        is_final = bool(payload.get("is_final", False))
        utterance = payload.get("utterance", {}) or {}
        text = (utterance.get("text") or payload.get("text") or "").strip()
        if not text:
            return None
        if not is_final and not self._receive_partials:
            return None
        logger.info(
            "Gladia Live transcript",
            text=text[:120],
            is_final=is_final,
        )
        return Transcript(
            text=text,
            is_final=is_final,
            confidence=utterance.get("confidence"),
            language=self._language,
        )

    async def send_audio(self, pcm16: bytes) -> None:
        """Queue a PCM16 frame for transmission (no-op in mock mode)."""
        if not self._live or self._closed or not pcm16:
            return
        await self._audio_q.put(pcm16)

    async def transcripts(self) -> AsyncIterator[Transcript]:
        """Async iterator over partial + final transcripts until the session ends."""
        if not self._live:
            return
        while True:
            item = await self._transcript_q.get()
            if item is _STOP_SENTINEL:
                return
            assert isinstance(item, Transcript)
            yield item

    async def finish(self) -> None:
        """End the Gladia session (stop_recording). Prefer keeping the socket
        open across turns — Gladia endpointing already finalizes utterances.
        Only call this on full session teardown via ``close()``.
        """
        if self._live and not self._closed:
            await self._audio_q.put(_STOP_SENTINEL)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for task in (self._send_task, self._recv_task):
            if task and not task.done():
                task.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # pragma: no cover
                pass
        self._live = False
