"""WebSocket session lifecycle — serialized turns, VAD ingress, teardown (R2/R5)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from core.buffers.policy import INBOUND_MIC_POLICY, BufferPolicy, OverflowPolicy
from core.buffers.typed_queue import TypedAsyncQueue
from core.fsm.events import SessionEvent
from core.fsm.states import SessionState
from core.listening.frame_slicer import FrameSlicer
from core.protocol.realtime import (
    PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_RANGE,
    ProtocolCompatibilityError,
    ProtocolNegotiation,
    negotiate_protocol,
)
from core.providers.mode import provider_runtime_status
from core.transport.native_websocket import NativeWebSocketTransport
from core.types.audio import AudioFrame
from core.types.events import ControlEventType
from core.types.resampler import Resampler
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig
from worker_raw.security.ws_policy import WSSecurityPolicy, WSSecurityViolation
from worker_raw.ws_constants import (
    MAX_AUDIO_FRAME_BYTES,
    PING_INTERVAL_SEC,
    PONG_DEADLINE_MULTIPLIER,
)


class ProtocolSessionError(RuntimeError):
    """A protocol failure already reported to and closed on the client."""


class WebSocketSessionRunner:
    """Manages one WS audio session: ingress queue, turn worker, ping/pong, teardown."""

    def __init__(
        self,
        websocket: Any,
        transport: NativeWebSocketTransport,
        orchestrator: PipelineOrchestrator,
        config: PipelineSessionConfig,
        client_sample_rate: int = 16000,
        release_admission: Callable[[], Awaitable[None]] | None = None,
        heartbeat_admission: Callable[[], Awaitable[bool]] | None = None,
        token_expires_at: float | None = None,
        token_refresh_url: str = "/v1/session/refresh",
        token_expiry_notice_sec: float = 30.0,
    ) -> None:
        self.websocket = websocket
        self.transport = transport
        self.orchestrator = orchestrator
        self.config = config
        self.client_sample_rate = client_sample_rate
        self._release_admission = release_admission
        self._heartbeat_admission = heartbeat_admission
        self.token_expires_at = token_expires_at
        self.token_refresh_url = token_refresh_url
        self.token_expiry_notice_sec = max(0.0, token_expiry_notice_sec)
        self._ingress_resampler: Resampler | None = (
            Resampler(source_rate=client_sample_rate, target_rate=16000)
            if client_sample_rate != 16000
            and client_sample_rate in Resampler.SUPPORTED_RATES
            else None
        )
        self.stop = asyncio.Event()
        self.last_pong_monotonic = time.monotonic()
        self._ingress_seq = 0
        self._ingress_queue: TypedAsyncQueue[AudioFrame] = TypedAsyncQueue(
            INBOUND_MIC_POLICY
        )
        self._turn_queue: TypedAsyncQueue[tuple[str, asyncio.Future[str] | None]] = (
            TypedAsyncQueue(
                BufferPolicy(
                    name="turn_queue",
                    maxsize=32,
                    overflow=OverflowPolicy.BLOCK,
                )
            )
        )
        self._active_turns: set[asyncio.Task[Any]] = set()
        self._finalized = False
        self._server_sequence = 0
        self._last_client_sequence = 0
        # Canonical framing is a transport invariant, not an optional feature.
        self._frame_slicer = FrameSlicer()
        self.security_policy = WSSecurityPolicy()

    def _track_turn(self, task: asyncio.Task[Any]) -> None:
        self._active_turns.add(task)
        task.add_done_callback(self._active_turns.discard)

    async def enqueue_voice_turn(self, text: str) -> None:
        """Queue a finalized STT utterance (live Gladia path). Dedupes empties."""
        cleaned = (text or "").strip()
        if not cleaned or self.stop.is_set():
            return
        await self._turn_queue.put((cleaned, None))

    async def request_graceful_stop(self, reason: str) -> None:
        """Stop intake and close the socket after the pipeline drains final audio."""
        self.stop.set()
        await self.transport.close(self.websocket)

    async def _apply_system_prompt_override(self, prompt: object) -> bool:
        """Apply a local-only prompt override or report a typed policy error."""

        if prompt in (None, ""):
            return False
        if not self.config.allow_unsafe_session_overrides:
            await self.transport.send_control_event(
                "error",
                {
                    "code": "SESSION_OVERRIDE_FORBIDDEN",
                    "message": (
                        "The system prompt is pinned by the published agent plan."
                    ),
                },
            )
            return False
        self.config.system_prompt = str(prompt)
        await self.transport.send_control_event(
            "info", {"message": "System prompt updated for local development session."}
        )
        return True

    async def start(self) -> None:
        workers: list[asyncio.Task[Any]] = []
        try:
            await self._perform_protocol_handshake()
            self.orchestrator.attach_ws_session(self)
            await self.orchestrator.apply_provider_selection(self.config)
            start_record = getattr(self.orchestrator, "start_session_record", None)
            if callable(start_record):
                await start_record(self.config)
            self.orchestrator.barge_in_controller.fsm = self.orchestrator.fsm
            self.orchestrator.barge_in_controller.cancel_contract = (
                self.orchestrator.three_point_cancel
            )
            self.orchestrator.apply_language_vad_overrides(self.config.language)
            if self.orchestrator.fsm.can_transition(SessionEvent.SESSION_ADMITTED):
                self.orchestrator.fsm.trigger(SessionEvent.SESSION_ADMITTED)
            self.orchestrator.vad_adapter.reset()
            streaming_stt_status = await self.orchestrator.prepare_live_stt()
            runtime_status = provider_runtime_status()
            await self.transport.send_control_event(
                ControlEventType.METRIC,
                {
                    "kind": "session_ready",
                    "session_id": self.config.session_id,
                    "streaming_stt": streaming_stt_status,
                    **runtime_status,
                },
            )
            greeting = (self.config.initial_greeting or "").strip()
            if greeting:
                await self._turn_queue.put((f"__greeting__:{greeting}", None))
            workers.extend(
                (
                    asyncio.create_task(self._ingress_worker()),
                    asyncio.create_task(self._turn_worker()),
                    asyncio.create_task(self._ping_loop()),
                )
            )
            if self.token_expires_at is not None:
                workers.append(asyncio.create_task(self._token_expiry_loop()))
            await self._receive_loop()
        finally:
            self.stop.set()
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            for t in list(self._active_turns):
                if not t.done():
                    t.cancel()
            await asyncio.gather(*list(self._active_turns), return_exceptions=True)
            try:
                await self.orchestrator.finalize_session(self.config)
            finally:
                try:
                    await self.transport.close(self.websocket)
                finally:
                    if self._release_admission is not None:
                        await self._release_admission()

    async def _perform_protocol_handshake(self) -> ProtocolNegotiation:
        """Require a compatible client hello before provider startup."""

        try:
            message = await asyncio.wait_for(self.websocket.receive(), timeout=5.0)
        except TimeoutError as exc:
            await self.transport.send_control_event(
                "error",
                {
                    "code": "PROTOCOL_HANDSHAKE_TIMEOUT",
                    "message": "protocol.hello was not received within 5 seconds",
                    "supported_range": SUPPORTED_PROTOCOL_RANGE,
                },
            )
            await self.websocket.close(code=4408, reason="protocol handshake timeout")
            raise ProtocolSessionError("PROTOCOL_HANDSHAKE_TIMEOUT") from exc

        raw = message.get("text") if isinstance(message, dict) else None
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
        except json.JSONDecodeError:
            data = {}
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        client_version = str(payload.get("protocol_version") or "")
        if data.get("event_type") != "protocol.hello" or not client_version:
            await self.transport.send_control_event(
                "error",
                {
                    "code": "PROTOCOL_HELLO_REQUIRED",
                    "message": "the first client event must be protocol.hello",
                    "supported_range": SUPPORTED_PROTOCOL_RANGE,
                },
            )
            await self.websocket.close(code=4400, reason="protocol hello required")
            raise ProtocolSessionError("PROTOCOL_HELLO_REQUIRED")

        try:
            envelope_version = str(data["protocol_version"])
            event_id = str(data["event_id"]).strip()
            sequence = int(data["sequence"])
            if not envelope_version or not event_id or sequence < 1:
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            await self.transport.send_control_event(
                "error",
                {
                    "code": "PROTOCOL_ENVELOPE_REQUIRED",
                    "message": (
                        "protocol.hello requires version, event_id, and sequence"
                    ),
                    "supported_range": SUPPORTED_PROTOCOL_RANGE,
                },
            )
            await self.websocket.close(code=4400, reason="protocol envelope required")
            raise ProtocolSessionError("PROTOCOL_ENVELOPE_REQUIRED") from exc

        try:
            negotiate_protocol(envelope_version)
            negotiated = negotiate_protocol(client_version)
        except ProtocolCompatibilityError as exc:
            await self.transport.send_control_event(
                "error",
                {
                    "code": exc.code,
                    "message": str(exc),
                    "client_version": exc.client_version,
                    "supported_range": exc.supported_range,
                },
            )
            await self.websocket.close(code=4406, reason="protocol version unsupported")
            raise ProtocolSessionError(exc.code) from exc

        await self.transport.send_control_event(
            "session.ready",
            {
                "protocol_version": PROTOCOL_VERSION,
                "supported_range": SUPPORTED_PROTOCOL_RANGE,
                "session_id": self.config.session_id,
                "resume_supported": False,
            },
        )
        self._last_client_sequence = sequence
        return negotiated

    async def _validate_client_envelope(
        self, data: dict[str, Any], event_type: str
    ) -> bool:
        """Enforce ordering for canonical v1 events; allow named legacy aliases."""

        legacy_aliases = {
            "barge_in",
            "text_turn",
            "user_turn",
            "ping",
            "pong",
            "playback_started",
            "set_prompt",
        }
        if event_type in legacy_aliases and "sequence" not in data:
            return True
        try:
            negotiate_protocol(str(data["protocol_version"]))
            sequence = int(data["sequence"])
            event_id = str(data["event_id"]).strip()
            if not event_id or sequence <= self._last_client_sequence:
                raise ValueError
        except (KeyError, TypeError, ValueError, ProtocolCompatibilityError):
            await self.transport.send_control_event(
                "error",
                {
                    "code": "PROTOCOL_SEQUENCE_INVALID",
                    "message": (
                        "canonical events require a unique event_id and "
                        "increasing sequence"
                    ),
                    "last_sequence": self._last_client_sequence,
                },
            )
            await self.websocket.close(code=4400, reason="protocol sequence invalid")
            self.stop.set()
            return False
        self._last_client_sequence = sequence
        return True

    async def _enqueue_pcm(self, pcm_data: bytes) -> None:
        """Slice (optional) and enqueue canonical PCM frames for ingress."""
        frames = self._frame_slicer.push(pcm_data)
        for pcm in frames:
            self._ingress_seq += 1
            frame = AudioFrame(
                pcm16=pcm,
                sample_rate=16000,
                channel_count=1,
                sequence=self._ingress_seq,
                timestamp_ms=time.time() * 1000.0,
            )
            wait_started = time.monotonic()
            await self._ingress_queue.put(frame)
            waited_ms = (time.monotonic() - wait_started) * 1000.0
            warn_ms = self.orchestrator.listening_config.ingress_backpressure_warn_ms
            if waited_ms >= warn_ms:
                await self.transport.send_control_event(
                    ControlEventType.METRIC,
                    {
                        "kind": "ingress_backpressure",
                        "waited_ms": round(waited_ms, 2),
                        "queue_size": self._ingress_queue.qsize(),
                        "dropped_frames": self._ingress_queue.drop_count,
                    },
                )

    async def _receive_loop(self) -> None:
        while not self.stop.is_set():
            message = await self.websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            try:
                self.security_policy.check_rate_limit(self.config.session_id)
            except WSSecurityViolation as exc:
                await self.transport.send_control_event(
                    "error",
                    {"code": "RATE_LIMIT_EXCEEDED", "message": str(exc)},
                )
                await self.websocket.close(code=1008, reason="rate limit exceeded")
                break

            if "bytes" in message and message["bytes"] is not None:
                pcm_data = message["bytes"]
                try:
                    self.security_policy.validate_frame_size(pcm_data)
                except WSSecurityViolation as exc:
                    await self.transport.send_control_event(
                        "error",
                        {
                            "code": "FRAME_TOO_LARGE",
                            "message": str(exc),
                            "max_bytes": MAX_AUDIO_FRAME_BYTES,
                        },
                    )
                    await self.websocket.close(code=1009, reason="frame too large")
                    break
                if self._ingress_resampler is not None:
                    pcm_data = self._ingress_resampler.process(pcm_data)
                await self._enqueue_pcm(pcm_data)
                continue
            text = message.get("text")
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            event_type = data.get("event_type") or data.get("type")
            if not isinstance(event_type, str):
                continue
            if not await self._validate_client_envelope(data, event_type):
                break
            if event_type == "session.close":
                self.stop.set()
                break
            if event_type in ("pong", "control.pong"):
                self.last_pong_monotonic = time.monotonic()
                continue
            if event_type in ("ping", "control.ping"):
                self.last_pong_monotonic = time.monotonic()
                await self.transport.send_control_event(
                    ControlEventType.PONG, {"t": time.time()}
                )
                continue
            if event_type == "set_prompt":
                await self._apply_system_prompt_override(data.get("system_prompt"))
                continue
            if event_type in ("text.turn", "text_turn", "user_turn"):
                payload_dict = (
                    data.get("payload") if isinstance(data.get("payload"), dict) else {}
                )
                user_text = str(
                    data.get("text") or payload_dict.get("text") or ""
                ).strip()
                new_prompt = data.get("system_prompt") or payload_dict.get(
                    "system_prompt"
                )
                if new_prompt:
                    await self._apply_system_prompt_override(new_prompt)
                if user_text:
                    if self.orchestrator.fsm.state in (
                        SessionState.AGENT_SPEAKING,
                        SessionState.PROCESSING_INFERENCE,
                        SessionState.BARGE_IN_VERIFY,
                    ):
                        await self.orchestrator.execute_immediate_barge_in(
                            reason="text turn interrupted active agent turn"
                        )
                    await self._turn_queue.put((user_text, None))
                continue
            if event_type in ("barge_in", ControlEventType.BARGE_IN.value):
                if event_type == "barge_in":
                    await self.transport.send_control_event(
                        "info",
                        {
                            "kind": "protocol_deprecation",
                            "alias": "barge_in",
                            "canonical": ControlEventType.BARGE_IN.value,
                            "removal": "next_protocol_major",
                        },
                    )
                reason = str(
                    (data.get("payload") or {}).get("reason") or "client_barge_in"
                )
                await self.orchestrator.execute_immediate_barge_in(reason=reason)
                continue
            if event_type == ControlEventType.CLEAR_AUDIO_ACK.value:
                payload = (
                    data.get("payload") if isinstance(data.get("payload"), dict) else {}
                )
                try:
                    await self.orchestrator.handle_clear_audio_ack(
                        turn_id=str(payload.get("turn_id") or ""),
                        sequence=int(payload.get("sequence") or 0),
                        played_audio_ms=float(payload.get("played_audio_ms") or 0.0),
                    )
                except (TypeError, ValueError):
                    pass
                continue
            if event_type == ControlEventType.PLAYBACK_DRAINED.value:
                payload = (
                    data.get("payload") if isinstance(data.get("payload"), dict) else {}
                )
                try:
                    await self.orchestrator.handle_playback_drained(
                        turn_id=str(payload.get("turn_id") or ""),
                        played_audio_ms=float(payload.get("played_audio_ms") or 0.0),
                    )
                except (TypeError, ValueError):
                    pass
                continue
            if event_type in (
                "metric",
                "playback_started",
                "control.playback_started",
                ControlEventType.PLAYBACK_STARTED.value,
            ):
                payload = (
                    data.get("payload")
                    if isinstance(data.get("payload"), dict)
                    else data
                )
                kind = str(payload.get("kind") or event_type or "")
                if kind in (
                    "playback_started",
                    ControlEventType.PLAYBACK_STARTED.value,
                ):
                    try:
                        turn_id = UUID(str(payload.get("turn_id") or ""))
                        acknowledge = (
                            self.orchestrator.latency_collector.acknowledge_playback
                        )
                        result = acknowledge(
                            turn_id=turn_id,
                            client_playback_started_ms=float(
                                payload.get("client_playback_started_ms")
                                or payload.get("t")
                                or 0.0
                            ),
                            client_scheduled_playback_ms=(
                                float(payload["client_scheduled_playback_ms"])
                                if payload.get("client_scheduled_playback_ms")
                                is not None
                                else None
                            ),
                            receipt_monotonic_ms=self.orchestrator.latency_hooks.now_ms(),
                            underrun=(
                                bool(payload["underrun"])
                                if payload.get("underrun") is not None
                                else None
                            ),
                            prebuffer_ms=(
                                float(payload["prebuffer_ms"])
                                if payload.get("prebuffer_ms") is not None
                                else None
                            ),
                        )
                    except (TypeError, ValueError):
                        continue
                    if result.accepted and result.waterfall is not None:
                        await self.orchestrator._emit_latency_telemetry(
                            result.waterfall
                        )
                continue

    async def _ingress_worker(self) -> None:
        while not self.stop.is_set():
            try:
                frame = await asyncio.wait_for(self._ingress_queue.get(), timeout=0.5)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            await self.orchestrator.process_frame_async(frame)
            if self.orchestrator._speech_end_pending:
                self.orchestrator._speech_end_pending = False
                try:
                    text = await self.orchestrator.transcribe_speech_buffer(self.config)
                except Exception:
                    text = ""
                if text:
                    await self._turn_queue.put((text, None))
                else:
                    self.orchestrator.resume_listening()

    async def _turn_worker(self) -> None:
        while not self.stop.is_set():
            try:
                user_text, _future = await asyncio.wait_for(
                    self._turn_queue.get(), timeout=0.5
                )
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            if user_text.startswith("__greeting__:"):
                phrase = user_text.split(":", 1)[1].strip() or "Hello."
                task = asyncio.create_task(
                    self.orchestrator.run_greeting(self.config, phrase)
                )
            else:
                # Coalesce rapid utterance fragments queued during inference.
                accumulated = [user_text]
                while not self._turn_queue.empty():
                    try:
                        extra, _ = self._turn_queue.get_nowait()
                        if extra and not extra.startswith("__greeting__:"):
                            accumulated.append(extra)
                    except Exception:
                        break
                combined_text = " ".join(accumulated).strip()
                task = asyncio.create_task(
                    self.orchestrator.run_turn(self.config, combined_text)
                )
            self._track_turn(task)
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    async def _ping_loop(self) -> None:
        deadline = PING_INTERVAL_SEC * PONG_DEADLINE_MULTIPLIER
        while not self.stop.is_set():
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=PING_INTERVAL_SEC)
                break
            except TimeoutError:
                pass
            if not self.transport.is_connected:
                break
            if self._heartbeat_admission is not None:
                try:
                    refreshed = await self._heartbeat_admission()
                except Exception:
                    refreshed = False
                if not refreshed:
                    self.stop.set()
                    await self.websocket.close(
                        code=1013, reason="session admission lease unavailable"
                    )
                    break
            if time.monotonic() - self.last_pong_monotonic > deadline:
                try:
                    await self.transport.send_control_event(
                        "session.close",
                        {
                            "code": "PONG_TIMEOUT",
                            "reason": "keepalive response deadline exceeded",
                            "retryable": True,
                        },
                    )
                    await self.websocket.close(code=1001, reason="pong timeout")
                except Exception:
                    pass
                self.stop.set()
                break
            await self.transport.send_control_event(
                "control.ping", {"interval_sec": PING_INTERVAL_SEC}
            )

    async def _wait_until_epoch(self, epoch_seconds: float) -> bool:
        """Return True when stopped early, False when the deadline arrives."""

        delay = max(0.0, epoch_seconds - time.time())
        try:
            await asyncio.wait_for(self.stop.wait(), timeout=delay)
        except TimeoutError:
            return False
        return True

    async def _token_expiry_loop(self) -> None:
        """Warn before JWT expiry, then close deterministically at expiry."""

        if self.token_expires_at is None:
            return
        notice_at = self.token_expires_at - self.token_expiry_notice_sec
        if await self._wait_until_epoch(notice_at):
            return
        await self.transport.send_control_event(
            "session.token_expiring",
            {
                "expires_at_ms": self.token_expires_at * 1000.0,
                "refresh_url": self.token_refresh_url,
            },
        )
        if await self._wait_until_epoch(self.token_expires_at):
            return
        await self.transport.send_control_event(
            "session.close",
            {
                "code": "TOKEN_EXPIRED",
                "reason": "session token expired",
                "retryable": True,
            },
        )
        await self.websocket.close(code=4401, reason="session token expired")
        self.stop.set()
