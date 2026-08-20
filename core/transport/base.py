"""UCVE Base Transport Gateway Protocol."""

from __future__ import annotations

from typing import Any, Protocol


class BaseTransportGateway(Protocol):
    """Protocol for real-time audio transport gateways (WebSocket, WebRTC, SIP)."""

    async def connect(self, connection_id: str, token: str) -> bool:
        """Authenticate and establish client audio transport connection."""
        ...

    async def send_audio_frame(self, frame_bytes: bytes) -> None:
        """Send outgoing PCM audio frame to client."""
        ...

    async def send_control_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Send JSON control event message to client (e.g. control.pong, control.metric)."""
        ...

    async def close(self) -> None:
        """Close client transport connection."""
        ...
