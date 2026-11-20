"""UCVE Sovereign Voice Client (Async Python)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import websockets

from .version import SDK_VERSION_MANIFEST


class SessionRejectedError(ConnectionError):
    """The worker accepted the socket and then refused the session.

    ``code`` is the WebSocket close code when the server sent one (4401
    invalid or expired session, 4403 forbidden, 1013 at capacity or
    draining). The session token is spent; mint a new session to retry.
    """

    def __init__(self, code: int | None, reason: str) -> None:
        self.code = code
        self.reason = reason
        label = f"{code} {reason}" if code is not None else reason
        super().__init__(f"Wavia worker rejected the session: {label}")


def _as_session_error(exc: Exception) -> SessionRejectedError:
    if isinstance(exc, SessionRejectedError):
        return exc
    if isinstance(exc, websockets.ConnectionClosed) and exc.rcvd is not None:
        return SessionRejectedError(exc.rcvd.code, exc.rcvd.reason or "closed")
    if isinstance(exc, asyncio.TimeoutError):
        return SessionRejectedError(None, "no session.ready before the handshake timeout")
    return SessionRejectedError(None, str(exc) or type(exc).__name__)


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
        demo_provider_overrides: dict[str, str] | None = None,
        allow_demo_provider_overrides: bool = False,
        handshake_timeout_sec: float = 5.0,
        max_connect_attempts: int = 3,
        reconnect_backoff_sec: float = 0.25,
        on_transcript: Callable[[str, str], Any] | None = None,
        on_audio: Callable[[bytes], Any] | None = None,
        on_audio_start: Callable[[dict[str, Any]], Any] | None = None,
        on_barge_in: Callable[[dict[str, Any]], Any] | None = None,
        on_clear_audio: Callable[[dict[str, Any]], Any] | None = None,
        on_played_text_commit: Callable[[dict[str, Any]], Any] | None = None,
        on_metric: Callable[[dict[str, Any]], Any] | None = None,
        on_degraded: Callable[[dict[str, Any]], Any] | None = None,
        on_token_expiring: Callable[[dict[str, Any]], Any] | None = None,
        on_close: Callable[[dict[str, Any]], Any] | None = None,
        on_error: Callable[[dict[str, Any]], Any] | None = None,
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
        if demo_provider_overrides and not allow_demo_provider_overrides:
            raise ValueError(
                "Provider overrides are demo-only; set "
                "allow_demo_provider_overrides=True only for a local demo."
            )
        allowed_demo_keys = {
            "stt_provider",
            "llm_provider",
            "llm_model",
            "tts_provider",
            "tts_voice_id",
        }
        unknown = set(demo_provider_overrides or {}) - allowed_demo_keys
        if unknown:
            raise ValueError(f"Unsupported demo override keys: {sorted(unknown)}")
        self.demo_provider_overrides = dict(demo_provider_overrides or {})
        self.handshake_timeout_sec = max(0.1, float(handshake_timeout_sec))
        self.max_connect_attempts = max(1, min(int(max_connect_attempts), 5))
        self.reconnect_backoff_sec = max(0.0, float(reconnect_backoff_sec))
        self.on_transcript = on_transcript
        self.on_audio = on_audio
        self.on_audio_start = on_audio_start
        self.on_barge_in = on_barge_in
        self.on_clear_audio = on_clear_audio
        self.on_played_text_commit = on_played_text_commit
        self.on_metric = on_metric
        self.on_degraded = on_degraded
        self.on_token_expiring = on_token_expiring
        self.on_close = on_close
        self.on_error = on_error
        self._ws: Any | None = None
        self._running = False
        self._listen_task: asyncio.Task[None] | None = None
        self._active_turn_id: str | None = None
        self._control_sequence = 0
        self._event_sequence = 0
        self.version_manifest = SDK_VERSION_MANIFEST

    @property
    def connection_url(self) -> str:
        """Return an encoded connection URL without mutating the base URL."""

        parts = urlsplit(self.ws_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update(
            {
                "token": self.token,
                "protocol_version": SDK_VERSION_MANIFEST["event_schema_version"],
            }
        )
        query.update(self.demo_provider_overrides)
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    def _build_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._event_sequence += 1
        return {
            "protocol_version": SDK_VERSION_MANIFEST["event_schema_version"],
            "event_id": str(uuid4()),
            "sequence": self._event_sequence,
            "event_type": event_type,
            "timestamp_ms": time.time() * 1000.0,
            "payload": payload,
        }

    def build_hello_event(self) -> dict[str, Any]:
        """Build the mandatory first event for protocol negotiation."""

        return self._build_event(
            "protocol.hello",
            {
                "protocol_version": SDK_VERSION_MANIFEST["event_schema_version"],
                "sdk": {
                    "name": "ucve-python",
                    "version": SDK_VERSION_MANIFEST["api_version"],
                },
                "capabilities": ["pcm16", "barge_in", "playback_ack"],
                "resume": None,
            },
        )

    def build_text_turn(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("text is required")
        return self._build_event("text.turn", {"text": cleaned})

    async def connect(self) -> None:
        """Establish the WebSocket and start the background receiver loop.

        Only failures to *reach* the worker are retried. Once a socket opens,
        the worker has consumed the single-use session token, so a rejection
        or failed handshake raises :class:`SessionRejectedError` with the
        server's close code and reason; mint a new session to try again.
        """
        last_error: Exception | None = None
        for attempt in range(self.max_connect_attempts):
            try:
                self._ws = await websockets.connect(self.connection_url)
            except (OSError, asyncio.TimeoutError, websockets.InvalidHandshake) as exc:
                last_error = exc
                if attempt + 1 >= self.max_connect_attempts:
                    raise ConnectionError(
                        f"Could not reach the Wavia worker: {exc}"
                    ) from exc
                await asyncio.sleep(self.reconnect_backoff_sec * (2**attempt))
                continue
            try:
                await self._handshake()
            except Exception as exc:
                await self._abandon_socket()
                raise _as_session_error(exc) from exc
            self._running = True
            self._listen_task = asyncio.create_task(self._listen_loop())
            return
        raise ConnectionError("WebSocket connection failed") from last_error

    async def _handshake(self) -> None:
        assert self._ws is not None
        await self._ws.send(json.dumps(self.build_hello_event()))
        raw_ready = await asyncio.wait_for(
            self._ws.recv(), timeout=self.handshake_timeout_sec
        )
        if not isinstance(raw_ready, str):
            raise ConnectionError("Server did not return a JSON session.ready event")
        ready = json.loads(raw_ready)
        if ready.get("event_type") != "session.ready":
            payload = ready.get("payload") or {}
            code = payload.get("code") or "protocol handshake failed"
            raise SessionRejectedError(None, str(code))

    async def _abandon_socket(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001 - already failing; keep the first error
                pass
            finally:
                self._ws = None

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
                        if event_type in ("ping", "control.ping"):
                            await self._ws.send(
                                json.dumps(self._build_event("control.pong", {}))
                            )
                        elif event_type in (
                            "transcript.final",
                            "transcript.partial",
                            "transcript",
                        ) and self.on_transcript:
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
                        elif event_type in ("audio.start", "audio_start"):
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
                        elif (
                            event_type in ("metric.latency", "metric")
                            and self.on_metric
                        ):
                            payload = data.get("payload") or data
                            res = self.on_metric(payload)
                            if asyncio.iscoroutine(res):
                                await res
                        elif event_type == "degraded" and self.on_degraded:
                            res = self.on_degraded(data.get("payload") or {})
                            if asyncio.iscoroutine(res):
                                await res
                        elif (
                            event_type == "session.token_expiring"
                            and self.on_token_expiring
                        ):
                            res = self.on_token_expiring(data.get("payload") or {})
                            if asyncio.iscoroutine(res):
                                await res
                        elif event_type == "error" and self.on_error:
                            res = self.on_error(data.get("payload") or {})
                            if asyncio.iscoroutine(res):
                                await res
                        elif event_type == "session.close":
                            self._running = False
                            if self.on_close:
                                res = self.on_close(data.get("payload") or {})
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

    async def send_text_turn(self, text: str) -> None:
        """Send one canonical text turn through the realtime pipeline."""

        if not self._ws:
            raise RuntimeError("Client is not connected. Call connect() first.")
        await self._ws.send(json.dumps(self.build_text_turn(text)))

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
        msg = self._build_event(
            "control.playback_started",
            {
                "kind": "playback_started",
                "turn_id": turn_id,
                "client_clock_domain": "client_performance_ms",
                "client_playback_started_ms": time.perf_counter() * 1000.0,
                "client_scheduled_playback_ms": client_scheduled_playback_ms,
                "audio_context_time_sec": audio_context_time_sec,
                "prebuffer_ms": prebuffer_ms,
                "underrun": underrun,
            },
        )
        await self._ws.send(json.dumps(msg))

    async def send_barge_in(self, rms: float = 0.08) -> None:
        """Trigger instant voice barge-in cancellation."""
        if not self._ws:
            return
        self._control_sequence += 1
        msg = self._build_event(
            "control.barge_in",
            {
                "rms": rms,
                "t": time.time() * 1000,
                "turn_id": self._active_turn_id,
                "sequence": self._control_sequence,
            },
        )
        await self._ws.send(json.dumps(msg))

    async def _ack_clear_audio(
        self, payload: dict[str, Any], played_audio_ms: float
    ) -> None:
        if not self._ws:
            return
        await self._ws.send(
            json.dumps(
                self._build_event(
                    "control.clear_audio_ack",
                    {
                        "turn_id": payload.get("turn_id"),
                        "sequence": int(payload.get("sequence") or 0),
                        "played_audio_ms": played_audio_ms,
                    },
                )
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
                self._build_event(
                    "control.playback_drained",
                    {
                        "turn_id": turn_id,
                        "played_audio_ms": max(0.0, played_audio_ms),
                    },
                )
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
