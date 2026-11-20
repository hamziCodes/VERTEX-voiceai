"""One-call Telnyx media, pipeline, admission, usage, and teardown owner."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from core.fsm.events import SessionEvent
from core.metering.kinds import TELEPHONY_SEC
from core.metering.usage_meter import UsageMeter
from core.runtime.admission import SessionAdmissionController
from core.transport.caller_id import CallerIdContext
from core.types.audio import AudioFrame
from core.types.events import ControlEventType
from telephony_gateway.adapters.telnyx_media_stream import (
    InboundAudioFrame,
    TelnyxMediaStreamAdapter,
)
from telephony_gateway.telnyx.media import (
    TelnyxMediaProtocolError,
    verify_media_websocket_signature,
)
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


class TelephonySessionConflictError(RuntimeError):
    pass


class TelephonySessionRegistry:
    """Prevent two local owners for one carrier call or internal session."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_session: dict[str, TelephonySessionSupervisor] = {}
        self._by_call: dict[str, TelephonySessionSupervisor] = {}

    @property
    def active_count(self) -> int:
        return len(self._by_session)

    async def register(self, supervisor: TelephonySessionSupervisor) -> None:
        session_id = supervisor.config.session_id
        call_id = supervisor.adapter.expected_call_control_id
        async with self._lock:
            if session_id in self._by_session or call_id in self._by_call:
                raise TelephonySessionConflictError("telephony session already owned")
            self._by_session[session_id] = supervisor
            self._by_call[call_id] = supervisor

    async def unregister(self, supervisor: TelephonySessionSupervisor) -> None:
        async with self._lock:
            if self._by_session.get(supervisor.config.session_id) is supervisor:
                self._by_session.pop(supervisor.config.session_id, None)
            call_id = supervisor.adapter.expected_call_control_id
            if self._by_call.get(call_id) is supervisor:
                self._by_call.pop(call_id, None)


class TelephonySessionSupervisor:
    """Drive one authenticated Telnyx call through the shared voice pipeline."""

    def __init__(
        self,
        *,
        adapter: TelnyxMediaStreamAdapter,
        orchestrator: PipelineOrchestrator,
        config: PipelineSessionConfig,
        caller_id: CallerIdContext,
        admission: SessionAdmissionController,
        registry: TelephonySessionRegistry,
        usage_meter: UsageMeter | None = None,
        startup_timeout_sec: float = 5.0,
        heartbeat_interval_sec: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
        ingress_queue_frames: int = 16,
    ) -> None:
        if ingress_queue_frames < 1:
            raise ValueError("ingress_queue_frames must be positive")
        self.adapter = adapter
        self.orchestrator = orchestrator
        self.config = config
        self.caller_id = caller_id
        self.admission = admission
        self.registry = registry
        self.usage_meter = usage_meter or UsageMeter()
        self.startup_timeout_sec = max(0.1, startup_timeout_sec)
        self.heartbeat_interval_sec = max(1.0, heartbeat_interval_sec)
        self.clock = clock
        self.transport = self
        self.stop_event = asyncio.Event()
        self._ready = asyncio.Event()
        self._ingress_queue: asyncio.Queue[InboundAudioFrame] = asyncio.Queue(
            maxsize=ingress_queue_frames
        )
        self._turn_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=32)
        self._tasks: list[asyncio.Task[None]] = []
        self._active_turns: set[asyncio.Task[str]] = set()
        self._media_started_at: float | None = None
        self._requested_end_reason: str | None = None
        self._finalize_lock = asyncio.Lock()
        self._finalized = False
        self._admitted = False
        self._registered = False
        self._pipeline_started = False
        self._turn_count = 0

    @property
    def tasks_alive(self) -> int:
        return sum(not task.done() for task in (*self._tasks, *self._active_turns))

    async def wait_ready(self, timeout: float = 2.0) -> None:
        await asyncio.wait_for(self._ready.wait(), timeout=timeout)

    def _validate_contract(self) -> None:
        if not self.config.plan_authoritative:
            raise ValueError("telephony requires an authoritative published plan")
        if not self.config.session_plan_ref or not self.config.session_plan_hash:
            raise ValueError("authoritative session plan identity is incomplete")
        if self.config.transport_type != "telephony":
            raise ValueError("telephony transport_type is required")
        UUID(self.config.session_id)
        UUID(self.config.tenant_id)
        UUID(self.config.agent_id)
        if self.caller_id.carrier != "telnyx":
            raise ValueError("Telnyx caller identity is required")
        if self.caller_id.sip_call_id != self.adapter.expected_call_control_id:
            raise ValueError("caller identity does not match media call")

    async def run(
        self,
        *,
        signature_header: str | None,
        timestamp_header: str | None,
        now: float | None = None,
    ) -> None:
        self._validate_contract()
        if not verify_media_websocket_signature(
            stream_url=self.adapter.expected_stream_url,
            signature_header=signature_header,
            timestamp_header=timestamp_header,
            public_key=self.adapter.public_key,
            now=now,
        ):
            raise TelnyxMediaProtocolError("invalid_media_signature")

        await self.registry.register(self)
        self._registered = True
        try:
            await self.admission.acquire(self.config.session_id, self.config.tenant_id)
            self._admitted = True
            self.config.caller_id = self.caller_id
            self.adapter.on_audio_frame = self._on_audio_frame
            self.orchestrator.on_audio_out = self.adapter.send_audio
            self.orchestrator.usage_meter = self.usage_meter
            self.orchestrator.attach_transport_session(self)
            self.orchestrator.set_end_conversation_hook(self._end_from_tool)
            await self.orchestrator.apply_provider_selection(self.config)
            await self.orchestrator.start_session_record(self.config)
            self._pipeline_started = True
            self.orchestrator.barge_in_controller.fsm = self.orchestrator.fsm
            self.orchestrator.barge_in_controller.cancel_contract = (
                self.orchestrator.three_point_cancel
            )
            self.orchestrator.apply_language_vad_overrides(self.config.language)
            if self.orchestrator.fsm.can_transition(SessionEvent.SESSION_ADMITTED):
                self.orchestrator.fsm.trigger(SessionEvent.SESSION_ADMITTED)
            self.orchestrator.vad_adapter.reset()
            await self.orchestrator.prepare_live_stt()

            await self.adapter.open(
                signature_header=signature_header,
                timestamp_header=timestamp_header,
                now=now,
            )
            await self.adapter.wait_started(timeout=self.startup_timeout_sec)
            self._media_started_at = self.clock()
            self.orchestrator.begin_session_timing()
            self._tasks = [
                asyncio.create_task(
                    self._ingress_worker(), name="telnyx-pipeline-ingress"
                ),
                asyncio.create_task(self._turn_worker(), name="telnyx-pipeline-turn"),
                asyncio.create_task(
                    self._heartbeat_loop(), name="telnyx-admission-heartbeat"
                ),
            ]
            self._ready.set()
            try:
                await asyncio.wait_for(
                    self.adapter.wait_closed(),
                    timeout=float(self.config.max_duration_sec),
                )
                self._requested_end_reason = (
                    self._requested_end_reason
                    or self.adapter.close_reason
                    or "carrier_stop"
                )
            except TimeoutError:
                self._requested_end_reason = "max_duration_reached"
                await self.adapter.close(reason=self._requested_end_reason)
            except TelnyxMediaProtocolError as exc:
                self._requested_end_reason = exc.code
        finally:
            self.stop_event.set()
            self._discard_pending_input()
            for task in self._tasks:
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            for active_turn in self._active_turns:
                active_turn.cancel()
            await asyncio.gather(*self._active_turns, return_exceptions=True)
            self._active_turns.clear()
            await self.adapter.close(
                reason=self._requested_end_reason or "worker_shutdown"
            )
            try:
                await self._finalize_once()
            finally:
                if self._admitted:
                    await self.admission.release(
                        self.config.session_id, self.config.tenant_id
                    )
                    self._admitted = False
                if self._registered:
                    await self.registry.unregister(self)
                    self._registered = False

    async def stop(self, reason: str = "worker_shutdown") -> None:
        if self._requested_end_reason is None:
            self._requested_end_reason = reason
        self.stop_event.set()
        self._discard_pending_input()
        await self.adapter.close(reason=self._requested_end_reason)

    def _discard_pending_input(self) -> None:
        for queue in (self._ingress_queue, self._turn_queue):
            while True:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                queue.task_done()

    async def enqueue_voice_turn(self, text: str) -> None:
        cleaned = text.strip()
        if cleaned and not self.stop_event.is_set():
            await self._turn_queue.put(cleaned)

    async def _on_audio_frame(self, frame: InboundAudioFrame) -> None:
        if not self.stop_event.is_set():
            await self._ingress_queue.put(frame)

    async def _ingress_worker(self) -> None:
        while not self.stop_event.is_set():
            frame = await self._ingress_queue.get()
            try:
                await self.orchestrator.process_frame_async(
                    AudioFrame(
                        pcm16=frame.pcm16,
                        sample_rate=16000,
                        timestamp_ms=float(frame.timestamp_ms),
                        sequence=frame.sequence_number,
                        channel_count=1,
                    )
                )
                if self.orchestrator._speech_end_pending:
                    self.orchestrator._speech_end_pending = False
                    text = await self.orchestrator.transcribe_speech_buffer(self.config)
                    if text:
                        await self._turn_queue.put(text)
                    else:
                        self.orchestrator.resume_listening()
            except asyncio.CancelledError:
                raise
            except Exception:
                await self.stop("pipeline_ingress_failure")
                return
            finally:
                self._ingress_queue.task_done()

    async def _turn_worker(self) -> None:
        while not self.stop_event.is_set():
            text = await self._turn_queue.get()
            if self._turn_count >= self.config.max_turns:
                self._turn_queue.task_done()
                await self.stop("max_turns_reached")
                return
            self._turn_count += 1
            turn = asyncio.create_task(
                self.orchestrator.run_turn(self.config, text),
                name="telnyx-pipeline-active-turn",
            )
            self._active_turns.add(turn)
            turn.add_done_callback(self._active_turns.discard)
            try:
                await turn
            except asyncio.CancelledError:
                if self.stop_event.is_set():
                    raise
            except Exception:
                await self.stop("provider_pipeline_failure")
                return
            finally:
                self._turn_queue.task_done()

    async def _heartbeat_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(), timeout=self.heartbeat_interval_sec
                )
            except TimeoutError:
                if not await self.admission.heartbeat(
                    self.config.session_id, self.config.tenant_id
                ):
                    await self.stop("admission_lease_lost")
                    return

    async def send_control_event(
        self, event_type: str | ControlEventType, payload: dict[str, Any]
    ) -> None:
        normalized = (
            event_type.value if isinstance(event_type, ControlEventType) else event_type
        )
        if normalized == ControlEventType.CLEAR_AUDIO.value:
            await self.adapter.clear_playback()
            await self.orchestrator.handle_clear_audio_ack(
                turn_id=str(payload.get("turn_id") or ""),
                sequence=int(payload.get("sequence") or 0),
                played_audio_ms=0.0,
            )
        elif normalized == "audio.end":
            await self.adapter.flush_audio()
            await self.orchestrator.handle_playback_drained(
                turn_id=str(payload.get("turn_id") or ""),
                played_audio_ms=float(payload.get("generated_audio_ms") or 0.0),
            )

    async def request_graceful_stop(self, reason: str) -> None:
        await self.stop(reason)

    async def _end_from_tool(self, _summary: str, _disposition: str) -> None:
        await self.stop("agent_end_conversation")

    async def _finalize_once(self) -> None:
        async with self._finalize_lock:
            if self._finalized:
                return
            self._finalized = True
            if not self._pipeline_started:
                if self._admitted:
                    await self.orchestrator.shutdown_runtime_resources()
                return
            duration = (
                max(0.0, self.clock() - self._media_started_at)
                if self._media_started_at is not None
                else 0.0
            )
            reason = (
                self._requested_end_reason
                or self.adapter.close_reason
                or "worker_shutdown"
            )
            self.orchestrator._session_end_reason = reason
            if reason not in {"carrier_stop", "agent_end_conversation"}:
                self.orchestrator._session_disposition = "unresolved"
            if duration > 0:
                await self.usage_meter.arecord(
                    self.config.tenant_id,
                    self.config.session_id,
                    TELEPHONY_SEC,
                    duration,
                    event_key=f"{self.config.session_id}:telephony_sec:final",
                    unit="seconds",
                )
                self.orchestrator.set_transport_usage(TELEPHONY_SEC, duration)
            await self.orchestrator.finalize_session(self.config)
