"""Telephony Abstraction Base — Core interfaces and normalized event models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class TelephonyEventType(StrEnum):
    """Normalized telephony event kinds."""

    CALL_STARTED = "call_started"
    CALL_ANSWERED = "call_answered"
    CALL_ENDED = "call_ended"
    DTMF = "dtmf"
    MEDIA_FRAME = "media_frame"


@dataclass
class TelephonyEvent:
    """Provider-agnostic telephony event data."""

    event_type: TelephonyEventType
    session_id: UUID
    from_number: str
    to_number: str
    timestamp_ms: int
    payload: dict[str, Any] = field(default_factory=dict)


class BaseTelephonyTransport(ABC):
    """Abstract base contract for all telephony transport adapters."""

    def __init__(self, session_id: UUID, from_number: str, to_number: str) -> None:
        self.session_id = session_id
        self.from_number = from_number
        self.to_number = to_number
        self.is_connected = False

    @abstractmethod
    async def connect() -> bool:
        """Establish transport leg connection."""
        pass

    @abstractmethod
    async def send_audio(self, pcm16_frame: bytes) -> None:
        """Send PCM16 16kHz audio frame egress."""
        pass

    @abstractmethod
    async def receive_audio(self) -> bytes | None:
        """Receive PCM16 16kHz audio frame ingress."""
        pass

    @abstractmethod
    async def hangup() -> None:
        """Terminate call session and cleanup resources."""
        pass

    @abstractmethod
    async def health_check() -> bool:
        """Return True if trunk/transport is healthy and reachable."""
        pass
