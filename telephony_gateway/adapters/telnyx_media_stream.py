"""Authenticated, bounded, paced Telnyx bidirectional media adapter."""

from __future__ import annotations

import asyncio
import base64
import binascii
import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from telephony_gateway.telnyx.media import (
    ConnectedFrame,
    DtmfFrame,
    ErrorFrame,
    MarkFrame,
    MediaFrame,
    MediaReorderBuffer,
    OrderedMediaPacket,
    StartFrame,
    StopFrame,
    TelnyxMediaProtocolError,
    TelnyxMediaState,
    parse_media_frame,
    verify_media_websocket_signature,
)
from telephony_gateway.transcoding.mulaw import (
    Pcm16Downsampler16To8,
    Pcm16Upsampler8To16,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
)
from telephony_gateway.transcoding.rebuffer import FixedFrameBuffer


class MediaSocket(Protocol):
    async def receive_text(self) -> str: ...

    async def send_json(self, payload: dict[str, Any]) -> None: ...

    async def close(self, code: int = 1000) -> None: ...


@dataclass(frozen=True, slots=True)
class InboundAudioFrame:
    pcm16: bytes
    sequence_number: int
    chunk: int
    timestamp_ms: int
    synthetic: bool = False


@dataclass(slots=True)
class TelnyxMediaMetrics:
    inbound_payload_bytes: int = 0
    outbound_payload_bytes: int = 0
    inbound_frames: int = 0
    outbound_frames: int = 0
    duplicate_chunks: int = 0
    late_chunks: int = 0
    lost_chunks: int = 0
    silence_frames: int = 0
    cleared_egress_frames: int = 0
    discarded_ingress_bytes: int = 0
    discarded_egress_bytes: int = 0
    max_ingress_queue_depth: int = 0
    max_egress_queue_depth: int = 0
    _ingress_processing_ms: list[float] = field(default_factory=list, repr=False)
    _egress_processing_ms: list[float] = field(default_factory=list, repr=False)

    @staticmethod
    def _p95(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = max(0, (95 * len(ordered) + 99) // 100 - 1)
        return ordered[index]

    @property
    def ingress_processing_p95_ms(self) -> float:
        return self._p95(self._ingress_processing_ms)

    @property
    def egress_processing_p95_ms(self) -> float:
        return self._p95(self._egress_processing_ms)


@dataclass(frozen=True, slots=True)
class _QueuedEgress:
    pcm16: bytes
    enqueued_at: float
    generation: int


_SENTINEL = object()


class TelnyxMediaStreamAdapter:
    """Own one authenticated Telnyx PCMU stream and its bounded worker tasks."""

    def __init__(
        self,
        *,
        socket: MediaSocket,
        expected_stream_url: str,
        expected_call_control_id: str,
        public_key: str,
        on_audio_frame: Callable[[InboundAudioFrame], Any],
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        ingress_queue_frames: int = 8,
        egress_queue_frames: int = 8,
        reorder_window: int = 2,
        max_loss_fill: int = 10,
    ) -> None:
        if ingress_queue_frames < 1 or egress_queue_frames < 1:
            raise ValueError("media queue sizes must be positive")
        if not expected_stream_url or not expected_call_control_id or not public_key:
            raise ValueError("media stream binding and public key are required")
        self.socket = socket
        self.expected_stream_url = expected_stream_url
        self.expected_call_control_id = expected_call_control_id
        self.public_key = public_key
        self.on_audio_frame = on_audio_frame
        self.clock = clock
        self.sleep = sleep
        self.state = TelnyxMediaState.NEW
        self.close_reason: str | None = None
        self.stream_id: str | None = None
        self.metrics = TelnyxMediaMetrics()
        self.dtmf_events: list[str] = []
        self.marks: list[str] = []
        self._reorder = MediaReorderBuffer(
            window=reorder_window, max_loss_fill=max_loss_fill
        )
        self._ingress_queue: asyncio.Queue[OrderedMediaPacket | object] = asyncio.Queue(
            maxsize=ingress_queue_frames
        )
        self._egress_queue: asyncio.Queue[_QueuedEgress | object] = asyncio.Queue(
            maxsize=egress_queue_frames
        )
        self._ingress_rebuffer = FixedFrameBuffer(160)
        self._egress_rebuffer = FixedFrameBuffer(640)
        self._upsampler = Pcm16Upsampler8To16()
        self._downsampler = Pcm16Downsampler16To8()
        self._started = asyncio.Event()
        self._closed = asyncio.Event()
        self._shutdown_signalled = False
        self._failure: TelnyxMediaProtocolError | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._supervisor: asyncio.Task[None] | None = None
        self._egress_lock = asyncio.Lock()
        self._socket_send_lock = asyncio.Lock()
        self._generation = 0
        self._fragment_metadata: OrderedMediaPacket | None = None
        self._egress_inflight = False

    @property
    def tasks_alive(self) -> int:
        return sum(not task.done() for task in self._tasks)

    @property
    def egress_inflight(self) -> bool:
        return self._egress_inflight

    async def open(
        self,
        *,
        signature_header: str | None,
        timestamp_header: str | None,
        now: float | None = None,
    ) -> None:
        if self.state is not TelnyxMediaState.NEW:
            raise RuntimeError("media adapter can only be opened once")
        if not verify_media_websocket_signature(
            stream_url=self.expected_stream_url,
            signature_header=signature_header,
            timestamp_header=timestamp_header,
            public_key=self.public_key,
            now=now,
        ):
            raise TelnyxMediaProtocolError("invalid_media_signature")
        self.state = TelnyxMediaState.OPEN
        self._tasks = [
            asyncio.create_task(self._receive_loop(), name="telnyx-media-receive"),
            asyncio.create_task(self._ingress_loop(), name="telnyx-media-ingress"),
            asyncio.create_task(self._egress_loop(), name="telnyx-media-egress"),
        ]
        self._supervisor = asyncio.create_task(
            self._supervise(), name="telnyx-media-supervisor"
        )

    async def wait_started(self, timeout: float = 1.0) -> None:
        await asyncio.wait_for(self._started.wait(), timeout=timeout)

    async def wait_closed(self, timeout: float = 2.0) -> None:
        await asyncio.wait_for(self._closed.wait(), timeout=timeout)
        if self._failure is not None:
            raise self._failure

    async def send_audio(self, pcm16: bytes) -> None:
        if self.state is not TelnyxMediaState.STARTED:
            raise TelnyxMediaProtocolError("media_stream_not_started")
        if len(pcm16) % 2:
            raise ValueError("PCM16 input length must be even")
        async with self._egress_lock:
            frames = self._egress_rebuffer.push(pcm16)
            generation = self._generation
        await self._queue_egress_frames(frames, generation=generation)

    async def flush_audio(self) -> None:
        """Pad and send a final partial 20 ms frame, then wait for carrier egress."""
        if self.state is not TelnyxMediaState.STARTED:
            return
        async with self._egress_lock:
            final_frame = self._egress_rebuffer.flush(pad_byte=0, pad=True)
            generation = self._generation
        if final_frame:
            await self._queue_egress_frames([final_frame], generation=generation)
        await self._egress_queue.join()

    async def wait_egress_drained(self) -> None:
        await self._egress_queue.join()

    async def _queue_egress_frames(
        self, frames: list[bytes], *, generation: int
    ) -> None:
        for frame in frames:
            queued = _QueuedEgress(
                pcm16=frame,
                enqueued_at=self.clock(),
                generation=generation,
            )
            await self._egress_queue.put(queued)
            self.metrics.max_egress_queue_depth = max(
                self.metrics.max_egress_queue_depth, self._egress_queue.qsize()
            )

    async def clear_playback(self) -> None:
        if self.state is not TelnyxMediaState.STARTED:
            return
        async with self._egress_lock:
            self._generation += 1
            if self._egress_inflight:
                self.metrics.cleared_egress_frames += 1
            discarded = self._egress_rebuffer.discard()
            self.metrics.discarded_egress_bytes += discarded
            if discarded:
                self.metrics.cleared_egress_frames += 1
            while True:
                try:
                    item = self._egress_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if item is not _SENTINEL:
                    self.metrics.cleared_egress_frames += 1
                self._egress_queue.task_done()
            self._downsampler.reset()
            async with self._socket_send_lock:
                await self.socket.send_json({"event": "clear"})

    async def close(self, *, reason: str = "application_close") -> None:
        if self._closed.is_set():
            return
        self.close_reason = reason
        await self._signal_shutdown(discard_egress=True)
        receiver = self._tasks[0] if self._tasks else None
        if receiver is not None and not receiver.done():
            receiver.cancel()
        if self._supervisor is not None:
            await self._supervisor

    async def _receive_loop(self) -> None:
        try:
            while not self._shutdown_signalled:
                try:
                    raw = await self.socket.receive_text()
                except EOFError as exc:
                    raise TelnyxMediaProtocolError(
                        "unexpected_media_disconnect"
                    ) from exc
                frame = parse_media_frame(raw)
                await self._handle_frame(frame)
                if isinstance(frame, StopFrame):
                    return
        except asyncio.CancelledError:
            return
        except TelnyxMediaProtocolError as exc:
            self._failure = exc
            self.state = TelnyxMediaState.ERROR
            self.close_reason = exc.code
            await self._signal_shutdown(discard_egress=True, discard_ingress=True)

    async def _handle_frame(self, frame: Any) -> None:
        if isinstance(frame, ConnectedFrame):
            if self.state is not TelnyxMediaState.OPEN:
                raise TelnyxMediaProtocolError("unexpected_connected_frame")
            self.state = TelnyxMediaState.CONNECTED
            return
        if isinstance(frame, StartFrame):
            if self.state is not TelnyxMediaState.CONNECTED:
                raise TelnyxMediaProtocolError("unexpected_start_frame")
            if frame.start.call_control_id != self.expected_call_control_id:
                raise TelnyxMediaProtocolError("media_call_identity_mismatch")
            self.stream_id = frame.stream_id
            self.state = TelnyxMediaState.STARTED
            self._started.set()
            return
        if isinstance(frame, ErrorFrame):
            raise TelnyxMediaProtocolError(f"carrier_media_error_{frame.payload.code}")
        if self.state is not TelnyxMediaState.STARTED:
            raise TelnyxMediaProtocolError("media_stream_not_started")
        if getattr(frame, "stream_id", None) != self.stream_id:
            raise TelnyxMediaProtocolError("media_stream_identity_mismatch")
        if isinstance(frame, MediaFrame):
            if frame.media.track != "inbound":
                return
            try:
                payload = base64.b64decode(frame.media.payload, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise TelnyxMediaProtocolError("invalid_media_payload") from exc
            if not payload:
                raise TelnyxMediaProtocolError("invalid_media_payload")
            self.metrics.inbound_payload_bytes += len(payload)
            packet = OrderedMediaPacket(
                sequence_number=frame.sequence_number,
                chunk=frame.media.chunk,
                timestamp_ms=frame.media.timestamp,
                payload=payload,
            )
            await self._enqueue_ingress(self._reorder.add(packet))
            self._sync_reorder_metrics()
            return
        if isinstance(frame, DtmfFrame):
            self.dtmf_events.append(frame.dtmf.digit)
            return
        if isinstance(frame, MarkFrame):
            self.marks.append(frame.mark.name)
            return
        if isinstance(frame, StopFrame):
            if frame.stop.call_control_id != self.expected_call_control_id:
                raise TelnyxMediaProtocolError("media_call_identity_mismatch")
            await self._enqueue_ingress(self._reorder.flush())
            self._sync_reorder_metrics()
            self.state = TelnyxMediaState.STOPPED
            self.close_reason = "carrier_stop"
            await self._signal_shutdown(discard_egress=True)

    async def _enqueue_ingress(self, packets: list[OrderedMediaPacket]) -> None:
        for packet in packets:
            await self._ingress_queue.put(packet)
            self.metrics.max_ingress_queue_depth = max(
                self.metrics.max_ingress_queue_depth, self._ingress_queue.qsize()
            )

    def _sync_reorder_metrics(self) -> None:
        self.metrics.duplicate_chunks = self._reorder.duplicate_chunks
        self.metrics.late_chunks = self._reorder.late_chunks
        self.metrics.lost_chunks = self._reorder.lost_chunks

    async def _ingress_loop(self) -> None:
        while True:
            item = await self._ingress_queue.get()
            try:
                if item is _SENTINEL:
                    remainder = self._ingress_rebuffer.flush(pad_byte=0xFF)
                    if remainder and self._fragment_metadata is not None:
                        await self._emit_ingress(remainder, self._fragment_metadata)
                    return
                assert isinstance(item, OrderedMediaPacket)
                if self._ingress_rebuffer.pending_bytes == 0:
                    self._fragment_metadata = item
                frames = self._ingress_rebuffer.push(item.payload)
                for index, payload in enumerate(frames):
                    metadata = self._fragment_metadata if index == 0 else item
                    await self._emit_ingress(payload, metadata or item)
                    self._fragment_metadata = None
                if self._ingress_rebuffer.pending_bytes:
                    self._fragment_metadata = self._fragment_metadata or item
            finally:
                self._ingress_queue.task_done()

    async def _emit_ingress(
        self, mulaw_payload: bytes, metadata: OrderedMediaPacket
    ) -> None:
        started = self.clock()
        if metadata.synthetic:
            self._upsampler.reset()
        pcm16 = self._upsampler.process(mulaw_to_pcm16(mulaw_payload))
        frame = InboundAudioFrame(
            pcm16=pcm16,
            sequence_number=metadata.sequence_number,
            chunk=metadata.chunk,
            timestamp_ms=metadata.timestamp_ms,
            synthetic=metadata.synthetic,
        )
        result = self.on_audio_frame(frame)
        if inspect.isawaitable(result):
            await result
        self.metrics.inbound_frames += 1
        if metadata.synthetic:
            self.metrics.silence_frames += 1
        self.metrics._ingress_processing_ms.append((self.clock() - started) * 1000.0)

    async def _egress_loop(self) -> None:
        next_deadline: float | None = None
        while True:
            item = await self._egress_queue.get()
            try:
                if item is _SENTINEL:
                    return
                assert isinstance(item, _QueuedEgress)
                if item.generation != self._generation:
                    self.metrics.cleared_egress_frames += 1
                    continue
                pcm8 = self._downsampler.process(item.pcm16)
                payload = pcm16_to_mulaw(pcm8)
                if len(payload) != 160:
                    raise TelnyxMediaProtocolError("invalid_egress_frame_size")
                if next_deadline is None:
                    next_deadline = self.clock()
                else:
                    next_deadline += 0.020
                    await self.sleep(max(0.0, next_deadline - self.clock()))
                self._egress_inflight = True
                try:
                    async with self._socket_send_lock:
                        if item.generation != self._generation:
                            self.metrics.cleared_egress_frames += 1
                            continue
                        await self.socket.send_json(
                            {
                                "event": "media",
                                "media": {
                                    "payload": base64.b64encode(payload).decode("ascii")
                                },
                            }
                        )
                finally:
                    self._egress_inflight = False
                self.metrics.outbound_frames += 1
                self.metrics.outbound_payload_bytes += len(payload)
                self.metrics._egress_processing_ms.append(
                    (self.clock() - item.enqueued_at) * 1000.0
                )
            except TelnyxMediaProtocolError as exc:
                self._failure = exc
                self.state = TelnyxMediaState.ERROR
                self.close_reason = exc.code
                return
            finally:
                self._egress_queue.task_done()

    async def _signal_shutdown(
        self, *, discard_egress: bool, discard_ingress: bool = False
    ) -> None:
        if self._shutdown_signalled:
            return
        self._shutdown_signalled = True
        if discard_ingress:
            self.metrics.discarded_ingress_bytes += self._ingress_rebuffer.discard()
            while True:
                try:
                    self._ingress_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                self._ingress_queue.task_done()
        if discard_egress:
            self.metrics.discarded_egress_bytes += self._egress_rebuffer.discard()
            while True:
                try:
                    item = self._egress_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if item is not _SENTINEL:
                    self.metrics.cleared_egress_frames += 1
                self._egress_queue.task_done()
        await self._ingress_queue.put(_SENTINEL)
        await self._egress_queue.put(_SENTINEL)

    async def _supervise(self) -> None:
        done, pending = await asyncio.wait(
            self._tasks, return_when=asyncio.FIRST_COMPLETED
        )
        if not self._shutdown_signalled:
            failure = next(
                (
                    task.exception()
                    for task in done
                    if not task.cancelled() and task.exception() is not None
                ),
                None,
            )
            if self._failure is None:
                detail = (
                    type(failure).__name__ if failure is not None else "worker_exit"
                )
                self._failure = TelnyxMediaProtocolError(
                    f"media_worker_failed_{detail}"
                )
            self.state = TelnyxMediaState.ERROR
            self.close_reason = self._failure.code
            self._shutdown_signalled = True
            for task in pending:
                task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.gather(*done, return_exceptions=True)
        await self.socket.close(code=1000 if self._failure is None else 1011)
        if self._failure is None:
            self.state = TelnyxMediaState.CLOSED
        self._closed.set()
