"""Optional Telnyx LiveKit SIP Adapter — Feature-flagged convenience wrap."""

from __future__ import annotations

from uuid import UUID

from core.transport.caller_id import CallerIdContext
from core.transport.livekit_sip import LiveKitSIPTransport
from telephony_gateway.base import BaseTelephonyTransport


class TelnyxLiveKitAdapter(BaseTelephonyTransport):
    """Optional LiveKit SIP participant adapter."""

    def __init__(self, session_id: UUID, from_number: str, to_number: str) -> None:
        super().__init__(session_id, from_number, to_number)
        self.caller_id = CallerIdContext(from_number=from_number, to_number=to_number)
        self.lk_sip = LiveKitSIPTransport(session_id=session_id, caller_id=self.caller_id)

    async def connect(self) -> bool:
        return await self.lk_sip.connect()

    async def send_audio(self, pcm16_frame: bytes) -> None:
        pass

    async def receive_audio(self) -> bytes | None:
        return None

    async def hangup(self) -> None:
        self.is_connected = False

    async def health_check(self) -> bool:
        return self.lk_sip.enabled
