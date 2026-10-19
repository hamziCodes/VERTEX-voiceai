"""UCVE Sovereign Voice Client (Async Python)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

import websockets

from sdk.python.ucve.version import SDK_VERSION_MANIFEST


class UCVEVoiceClient:
    """Async client for connecting to sovereign UCVE realtime audio streaming sessions.

    Strict zero-secret pattern: accepts only an ephemeral session token minted by
    your host backend. Raw tenant or provider API keys are strictly rejected.
    """

    def __init__(
        self,
        token: str,
        ws_url: str = "ws://localhost:8081/ws/audio",
        *,
        stt_provider: str = "gladia",
        llm_provider: str = "groq",
        tts_provider: str = "cartesia",
        on_transcript: Callable[[str, str], Any] | None = None,
        on_audio: Callable[[bytes], Any] | None = None,
        on_audio_start: Callable[[dict[str, Any]], Any] | None = None,
        on_barge_in: Callable[[dict[str, Any]], Any] | None = None,
        on_clear_audio: Callable[[dict[str, Any]], Any] | None = None,
        on_played_text_commit: Callable[[dict[str, Any]], Any] | None = None,
        on_metric: Callable[[dict[str, Any]], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        # Strict zero-secret constructor validation
        for forbidden in ("api_key", "secret", "private_key", "tenant_secret"):
            if forbidden in kwargs or forbidden in token.lower() and "=" in token:
                raise ValueError(
                    f"Client SDK must never accept raw '{forbidden}'. "
                    "Mint an ephemeral session token on your host backend instead."
                )

        if not token or not token.strip():
            raise ValueError(
                "An ephemeral session token is required to initialize "
                "UCVEVoiceClient."
            )

        self.token = token.strip()
        self.ws_url = ws_url.strip()
        self.stt_provider = stt_provider
        self.llm_provider = llm_provider
        self.tts_provider = tts_provider
        self.on_transcript = on_transcript
        self.on_audio = on_audio
        self.on_audio_start = on_audio_start
        self.on_barge_in = on_barge_in
        self.on_clear_audio = on_clear_audio
        self.on_played_text_commit = on_played_text_commit
        self.on_metric = on_metric
        self._ws: Any | None = None
        self._running = False
        self._listen_task: asyncio.Task[None] | None = None
        self._active_turn_id: str | None = None
        self._control_sequence = 0
        self.version_manifest = SDK_VERSION_MANIFEST

    async def connect(self) -> None:
        """Establish the WebSocket and start the background receiver loop."""
        url = self.ws_url
        separator = "&" if "?" in url else "?"
        query = (
            f"token={self.token}"
            f"&stt_provider={self.stt_provider}"
            f"&llm_provider={self.llm_provider}"
            f"&tts_provider={self.tts_provider}"
        )
        full_url = f"{url}{separator}{query}"
        self._ws = await websockets.connect(full_url)
        self._running = True
        self._listen_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self) -> None:
        """Background receiver loop routing incoming audio and control events."""
        while self._running and self._ws:
            try:
                message = await self._ws.recv()
                if isinstance(message, bytes):
                    if self.on_audio:
                        res = self.on_audio(message)
                        if asyncio.iscoroutine(res):
                            await res
                elif isinstance(message, str):
                    try:
                        data = json.loads(message)
                        event_type = data.get("event_type") or data.get("type")
                        if event_type == "transcript" and self.on_transcript:
                            payload = data.get("payload", {})
                            speaker = (
                                payload.get("speaker")
                                or data.get("speaker")
                                or "agent"
                            )
                            text = payload.get("text") or data.get("text") or ""
                            res = self.on_transcript(speaker, text)
                            if asyncio.iscoroutine(res):
                                await res
                        elif event_type == "audio_start":
                            payload = data.get("payload") or {}
                            turn_id = str(payload.get("turn_id") or "")
                            self._active_turn_id = turn_id or None
                            if self.on_audio_start:
                                res = self.on_audio_start(payload)
                                if asyncio.iscoroutine(res):
                                    await res
                        elif event_type in ("control.barge_in", "barge_in"):
                            payload = data.get("payload") or {}
                            if self.on_barge_in:
                                res = self.on_barge_in(payload)
                                if asyncio.iscoroutine(res):
                                    await res
                        elif event_type == "control.clear_audio":
                            payload = data.get("payload") or {}
                            played_audio_ms = 0.0
                            if self.on_clear_audio:
                                res = self.on_clear_audio(payload)
                                if asyncio.iscoroutine(res):
                                    res = await res
                                if isinstance(res, (int, float)):
                                    played_audio_ms = max(0.0, float(res))
                            await self._ack_clear_audio(payload, played_audio_ms)
                            self._active_turn_id = None
                        elif event_type == "assistant.played_text_commit":
                            payload = data.get("payload") or {}
                            if self.on_played_text_commit:
                                res = self.on_played_text_commit(payload)
                                if asyncio.iscoroutine(res):
                                    await res
                        elif event_type == "metric" and self.on_metric:
                            payload = data.get("payload") or data
                            res = self.on_metric(payload)
                            if asyncio.iscoroutine(res):
                                await res
                    except json.JSONDecodeError:
                        pass
            except asyncio.CancelledError:
                break
            except Exception:
                if not self._running:
                    break
                await asyncio.sleep(0.01)

    async def send_audio(self, pcm16_bytes: bytes) -> None:
        """Stream a raw 16 kHz mono 16-bit PCM chunk to the voice pipeline."""
        if not self._ws:
            raise RuntimeError("Client is not connected. Call connect() first.")
        await self._ws.send(pcm16_bytes)

    async def emit_playback_started(
        self,
        turn_id: str,
        *,
        client_scheduled_playback_ms: float | None = None,
        audio_context_time_sec: float | None = None,
        prebuffer_ms: float | None = None,
        underrun: bool | None = None,
    ) -> None:
        """Report actual playback onset for one server-issued turn ID."""
        if not self._ws:
            return
        if not turn_id.strip():
            raise ValueError("turn_id is required for playback correlation")
        msg = {
            "event_type": "control.playback_started",
            "payload": {
                "kind": "playback_started",
                "turn_id": turn_id,
                "client_clock_domain": "client_performance_ms",
                "client_playback_started_ms": time.perf_counter() * 1000.0,
                "client_scheduled_playback_ms": client_scheduled_playback_ms,
                "audio_context_time_sec": audio_context_time_sec,
                "prebuffer_ms": prebuffer_ms,
                "underrun": underrun,
            },
        }
        await self._ws.send(json.dumps(msg))

    async def send_barge_in(self, rms: float = 0.08) -> None:
        """Trigger instant voice barge-in cancellation."""
        if not self._ws:
            return
        self._control_sequence += 1
        msg = {
            "event_type": "control.barge_in",
            "payload": {
                "rms": rms,
                "t": time.time() * 1000,
                "turn_id": self._active_turn_id,
                "sequence": self._control_sequence,
            },
        }
        await self._ws.send(json.dumps(msg))

    async def _ack_clear_audio(
        self, payload: dict[str, Any], played_audio_ms: float
    ) -> None:
        if not self._ws:
            return
        await self._ws.send(
            json.dumps(
                {
                    "event_type": "control.clear_audio_ack",
                    "payload": {
                        "turn_id": payload.get("turn_id"),
                        "sequence": int(payload.get("sequence") or 0),
                        "played_audio_ms": played_audio_ms,
                    },
                }
            )
        )

    async def emit_playback_drained(
        self, turn_id: str, *, played_audio_ms: float
    ) -> None:
        """Confirm that all scheduled audio for a turn reached the speaker."""
        if not self._ws:
            return
        await self._ws.send(
            json.dumps(
                {
                    "event_type": "control.playback_drained",
                    "payload": {
                        "turn_id": turn_id,
                        "played_audio_ms": max(0.0, played_audio_ms),
                    },
                }
            )
        )
        if self._active_turn_id == turn_id:
            self._active_turn_id = None

    async def disconnect(self) -> None:
        """Gracefully close the streaming session."""
        self._running = False
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None
