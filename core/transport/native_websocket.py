"""UCVE Native WebSocket Transport Gateway."""

from __future__ import annotations

from typing import Any

from control_plane.auth.jwt import verify_session_jwt
from core.observability.logging import get_logger

logger = get_logger("ucve.transport.ws")


class NativeWebSocketTransport:
    """Sovereign plane native WebSocket transport handling binary audio & control messages."""

    def __init__(self) -> None:
        self.is_connected: bool = False
        self.session_id: str | None = None
        self.tenant_id: str | None = None

    async def connect(self, connection_id: str, token: str) -> bool:
        """Authenticate JWT token (from ?token= query param) and accept WS connection."""
        try:
            payload = verify_session_jwt(token)
            self.session_id = payload.get("sub")
            self.tenant_id = payload.get("tenant_id")
            self.is_connected = True
            return True
        except Exception as exc:
            logger.warning("WS authentication failure", error=str(exc))
            self.is_connected = False
            return False

    async def send_audio_frame(self, frame_bytes: bytes) -> None:
        """Send 16kHz PCM audio frame to client."""
        if not self.is_connected:
            raise ConnectionError("WS transport is disconnected.")

    async def send_control_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Send JSON control event (control.pong, control.metric)."""
        if not self.is_connected:
            raise ConnectionError("WS transport is disconnected.")

    async def close(self) -> None:
        """Close WebSocket connection."""
        self.is_connected = False
