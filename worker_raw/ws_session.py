"""WebSocket session lifecycle — serialized turns, VAD ingress, teardown (R2/R5)."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from uuid import uuid4

from core.buffers.policy import INBOUND_MIC_POLICY
from core.buffers.policy import BufferPolicy, OverflowPolicy
from core.buffers.typed_queue import TypedAsyncQueue
from core.fsm.events import SessionEvent
from core.latency.playback import PlaybackMetricHandler
from core.listening.frame_slicer import FrameSlicer
from core.transport.native_websocket import NativeWebSocketTransport
from core.types.audio import AudioFrame
from core.types.events import ControlEventType
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig
from worker_raw.ws_constants import MAX_AUDIO_FRAME_BYTES, PING_INTERVAL_SEC, PONG_DEADLINE_MULTIPLIER


class WebSocketSessionRunner:
    """Manages one WS audio session: ingress queue, turn worker, ping/pong, teardown."""

    def __init__(
        self,
        websocket: Any,
        transport: NativeWebSocketTransport,
        orchestrator: PipelineOrchestrator,
        config: PipelineSessionConfig,
    ) -> None:
        self.websocket = websocket
        self.transport = transport
        self.orchestrator = orchestrator
        self.config = config
        self.stop = asyncio.Event()
        self.last_pong_monotonic = time.monotonic()
        self._ingress_seq = 0
        self._ingress_queue: TypedAsyncQueue[AudioFrame] = TypedAsyncQueue(INBOUND_MIC_POLICY)
        self._turn_queue: TypedAsyncQueue[tuple[str, asyncio.Future[str] | None]] = TypedAsyncQueue(
            BufferPolicy(name="turn_queue", maxsize=32, overflow=OverflowPolicy.BLOCK)
        )
        self._active_turns: set[asyncio.Task[Any]] = set()
        self._finalized = False
        self._frame_slicer: FrameSlicer | None = (
            FrameSlicer()
            if orchestrator.listening_config.enable_frame_slicing
            else None
        )

    def _track_turn(self, task: asyncio.Task[Any]) -> None:
        self._active_turns.add(task)
        task.add_done_callback(self._active_turns.discard)

    async def enqueue_voice_turn(self, text: str) -> None:
        """Queue a finalized STT utterance (live Gladia path). Dedupes empties."""
        cleaned = (text or "").strip()
        if not cleaned or self.stop.is_set():
            return
        await self._turn_queue.put((cleaned, None))

    async def start(self) -> None:
        self.orchestrator.attach_ws_session(self)
        self.orchestrator.barge_in_controller.fsm = self.orchestrator.fsm
        self.orchestrator.barge_in_controller.cancel_contract = (
            self.orchestrator.three_point_cancel
        )
        self.orchestrator.apply_language_vad_overrides(self.config.language)
        if self.orchestrator.fsm.can_transition(SessionEvent.SESSION_ADMITTED):
            self.orchestrator.fsm.trigger(SessionEvent.SESSION_ADMITTED)
        self.orchestrator.vad_adapter.reset()
        # Open Gladia Live once for the whole call (legacy pattern).
        await self.orchestrator._maybe_start_live_stt()
        await self.transport.send_control_event(
            ControlEventType.METRIC,
            {"kind": "session_ready", "session_id": self.config.session_id},
        )
        greeting = (self.config.initial_greeting or "").strip()
        if greeting:
            # Queue as a synthetic user turn that TTS will speak via run_turn.
            await self._turn_queue.put((f"__greeting__:{greeting}", None))
        workers = [
            asyncio.create_task(self._ingress_worker()),
            asyncio.create_task(self._turn_worker()),
            asyncio.create_task(self._ping_loop()),
        ]
        try:
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
            await self.orchestrator.finalize_session(self.config)
            await self.transport.close(self.websocket)

    async def _enqueue_pcm(self, pcm_data: bytes) -> None:
        """Slice (optional) and enqueue canonical PCM frames for ingress."""
        if self._frame_slicer is not None:
            frames = self._frame_slicer.push(pcm_data)
        else:
            frames = [pcm_data] if pcm_data else []
        for pcm in frames:
            self._ingress_seq += 1
            frame = AudioFrame(
                pcm16=pcm,
                sample_rate=16000,
                channel_count=1,
                sequence=self._ingress_seq,
                timestamp_ms=time.time() * 1000.0,
            )
            await self._ingress_queue.put(frame)

    async def _receive_loop(self) -> None:
        while not self.stop.is_set():
            message = await self.websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                pcm_data = message["bytes"]
                if len(pcm_data) > MAX_AUDIO_FRAME_BYTES:
                    await self.transport.send_control_event(
                        "error",
                        {
                            "code": "FRAME_TOO_LARGE",
                            "max_bytes": MAX_AUDIO_FRAME_BYTES,
                        },
                    )
                    await self.websocket.close(code=1009, reason="frame too large")
                    break
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
            if event_type in ("pong", "control.pong"):
                self.last_pong_monotonic = time.monotonic()
                continue
            if event_type in ("ping", "control.ping"):
                await self.transport.send_control_event(
                    ControlEventType.PONG, {"t": time.time()}
                )
                continue
            if event_type == "set_prompt":
                new_prompt = data.get("system_prompt")
                if new_prompt:
                    self.config.system_prompt = str(new_prompt)
                    await self.transport.send_control_event(
                        "info", {"message": "System prompt updated for session."}
                    )
                continue
            if event_type in ("text_turn", "user_turn"):
                payload_dict = (
                    data.get("payload") if isinstance(data.get("payload"), dict) else {}
                )
                user_text = str(
                    data.get("text") or payload_dict.get("text") or ""
                ).strip()
                new_prompt = data.get("system_prompt") or payload_dict.get("system_prompt")
                if new_prompt:
                    self.config.system_prompt = str(new_prompt)
                if user_text:
                    await self._turn_queue.put((user_text, None))
                continue
            if event_type == "barge_in":
                self.orchestrator.three_point_cancel.execute_cancel_and_flush()
                await self.transport.send_control_event(
                    ControlEventType.BARGE_IN, data.get("payload") or {}
                )
                continue
            if event_type in ("metric", "playback_started", ControlEventType.PLAYBACK_STARTED.value):
                payload = data.get("payload") if isinstance(data.get("payload"), dict) else data
                kind = str(payload.get("kind") or event_type or "")
                if kind in ("playback_started", ControlEventType.PLAYBACK_STARTED.value):
                    waterfall = getattr(self.orchestrator, "_current_waterfall", None)
                    if waterfall is not None:
                        client_t = float(
                            payload.get("t") or payload.get("timestamp_ms") or 0.0
                        )
                        PlaybackMetricHandler.handle_playback_started(waterfall, client_t)
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
                waterfall = self.orchestrator.latency_hooks.start_turn(uuid4())
                task = asyncio.create_task(
                    self.orchestrator._finish_turn_tts(
                        [phrase], self.config, waterfall
                    )
                )
            else:
                task = asyncio.create_task(
                    self.orchestrator.run_turn(self.config, user_text)
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
            if time.monotonic() - self.last_pong_monotonic > deadline:
                try:
                    await self.websocket.close(code=1001, reason="pong timeout")
                except Exception:
                    pass
                self.stop.set()
                break
            await self.transport.send_control_event(
                "ping", {"interval_sec": PING_INTERVAL_SEC}
            )
