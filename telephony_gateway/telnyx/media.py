"""Strict Telnyx media WebSocket protocol and bounded reorder policy."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from telephony_gateway.telnyx.signature import verify_telnyx_signature


class TelnyxMediaProtocolError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TelnyxMediaState(StrEnum):
    NEW = "new"
    OPEN = "open"
    CONNECTED = "connected"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"
    CLOSED = "closed"


class ConnectedFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["connected"]
    version: str = Field(min_length=1, max_length=32)


class MediaFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    encoding: Literal["PCMU"]
    sample_rate: Literal[8000]
    channels: Literal[1]


class StartPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    call_control_id: str = Field(min_length=1, max_length=512)
    call_session_id: str = Field(min_length=1, max_length=128)
    media_format: MediaFormat


class StartFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["start"]
    sequence_number: int = Field(ge=0)
    stream_id: str = Field(min_length=1, max_length=128)
    start: StartPayload


class MediaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track: Literal["inbound", "outbound"]
    chunk: int = Field(ge=1)
    timestamp: int = Field(ge=0)
    payload: str = Field(min_length=1, max_length=512 * 1024)


class MediaFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["media"]
    sequence_number: int = Field(ge=0)
    stream_id: str = Field(min_length=1, max_length=128)
    media: MediaPayload


class StopPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    call_control_id: str = Field(min_length=1, max_length=512)


class StopFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["stop"]
    sequence_number: int = Field(ge=0)
    stream_id: str = Field(min_length=1, max_length=128)
    stop: StopPayload


class DtmfPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digit: str = Field(pattern=r"^[0-9A-D*#]$")


class DtmfFrame(BaseModel):
    model_config = ConfigDict(extra="allow")
    event: Literal["dtmf"]
    stream_id: str
    sequence_number: int = Field(ge=0)
    dtmf: DtmfPayload


class MarkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)


class MarkFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["mark"]
    stream_id: str
    sequence_number: int = Field(ge=0)
    mark: MarkPayload


class ErrorPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: int
    title: str = Field(min_length=1, max_length=128)
    detail: str = Field(default="", max_length=1024)


class ErrorFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["error"]
    stream_id: str | None = None
    payload: ErrorPayload


TelnyxMediaFrame = (
    ConnectedFrame
    | StartFrame
    | MediaFrame
    | StopFrame
    | DtmfFrame
    | MarkFrame
    | ErrorFrame
)

_FRAME_MODELS: dict[str, type[BaseModel]] = {
    "connected": ConnectedFrame,
    "start": StartFrame,
    "media": MediaFrame,
    "stop": StopFrame,
    "dtmf": DtmfFrame,
    "mark": MarkFrame,
    "error": ErrorFrame,
}


def parse_media_frame(raw: str) -> TelnyxMediaFrame:
    try:
        payload: Any = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("frame must be an object")
        event = payload.get("event")
        if not isinstance(event, str):
            raise ValueError("event must be a string")
        model = _FRAME_MODELS.get(event)
        if model is None:
            raise ValueError("unsupported event")
        return cast(TelnyxMediaFrame, model.model_validate(payload))
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise TelnyxMediaProtocolError("malformed_media_frame") from exc


def verify_media_websocket_signature(
    *,
    stream_url: str,
    signature_header: str | None,
    timestamp_header: str | None,
    public_key: str,
    now: float | None = None,
    max_drift_sec: float = 300.0,
) -> bool:
    """Verify Telnyx's signature over the exact configured media URL."""

    return bool(
        verify_telnyx_signature(
            stream_url.encode("utf-8"),
            signature_header,
            timestamp_header,
            public_key=public_key,
            now=now,
            max_drift_sec=max_drift_sec,
        )
    )


@dataclass(frozen=True, slots=True)
class OrderedMediaPacket:
    sequence_number: int
    chunk: int
    timestamp_ms: int
    payload: bytes
    synthetic: bool = False


class MediaReorderBuffer:
    """Reorder by Telnyx chunk, fill bounded loss, and drop repeats/late data."""

    def __init__(self, *, window: int = 2, max_loss_fill: int = 10) -> None:
        if window < 0 or max_loss_fill < 1:
            raise ValueError("invalid reorder policy")
        self.window = window
        self.max_loss_fill = max_loss_fill
        self.expected_chunk = 1
        self._pending: dict[int, OrderedMediaPacket] = {}
        self._seen: set[int] = set()
        self._seen_order: deque[int] = deque()
        self._history_size = max(32, window + max_loss_fill + 1)
        self.duplicate_chunks = 0
        self.late_chunks = 0
        self.lost_chunks = 0

    def add(self, packet: OrderedMediaPacket) -> list[OrderedMediaPacket]:
        if packet.chunk in self._seen or packet.chunk in self._pending:
            self.duplicate_chunks += 1
            return []
        if packet.chunk < self.expected_chunk:
            self.late_chunks += 1
            return []
        gap = packet.chunk - self.expected_chunk
        if gap > self.max_loss_fill:
            raise TelnyxMediaProtocolError("media_gap_exceeded")
        self._pending[packet.chunk] = packet
        output: list[OrderedMediaPacket] = []
        if gap > self.window:
            output.extend(self._fill_until(packet.chunk - self.window))
        output.extend(self._drain_contiguous())
        return output

    def flush(self) -> list[OrderedMediaPacket]:
        if not self._pending:
            return []
        highest = max(self._pending)
        if highest - self.expected_chunk > self.max_loss_fill:
            raise TelnyxMediaProtocolError("media_gap_exceeded")
        output = self._fill_until(highest + 1)
        output.extend(self._drain_contiguous())
        return output

    @property
    def tracked_chunk_count(self) -> int:
        return len(self._pending) + len(self._seen)

    def _remember(self, chunk: int) -> None:
        self._seen.add(chunk)
        self._seen_order.append(chunk)
        while len(self._seen_order) > self._history_size:
            self._seen.discard(self._seen_order.popleft())

    def _fill_until(self, exclusive: int) -> list[OrderedMediaPacket]:
        output: list[OrderedMediaPacket] = []
        while self.expected_chunk < exclusive:
            packet = self._pending.pop(self.expected_chunk, None)
            if packet is None:
                packet = OrderedMediaPacket(
                    sequence_number=-1,
                    chunk=self.expected_chunk,
                    timestamp_ms=self.expected_chunk * 20,
                    payload=b"\xff" * 160,
                    synthetic=True,
                )
                self.lost_chunks += 1
            self._remember(self.expected_chunk)
            output.append(packet)
            self.expected_chunk += 1
        return output

    def _drain_contiguous(self) -> list[OrderedMediaPacket]:
        output: list[OrderedMediaPacket] = []
        while self.expected_chunk in self._pending:
            packet = self._pending.pop(self.expected_chunk)
            self._remember(self.expected_chunk)
            output.append(packet)
            self.expected_chunk += 1
        return output
