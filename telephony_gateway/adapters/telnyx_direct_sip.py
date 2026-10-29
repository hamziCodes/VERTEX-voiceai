"""Telnyx Direct SIP Transport Adapter — Primary Sovereign PSTN Transport."""

from __future__ import annotations

from uuid import UUID

from core.transport.caller_id import CallerIdContext
from core.transport.direct_sip import DirectSIPTransport
from telephony_gateway.base import BaseTelephonyTransport


class TelnyxDirectSIPAdapter(BaseTelephonyTransport):
    """Wraps DirectSIPTransport under BaseTelephonyTransport contract."""

    def __init__(self, session_id: UUID, from_number: str, to_number: str) -> None:
        super().__init__(session_id, from_number, to_number)
        self.caller_id = CallerIdContext(
            from_number=from_number,
            to_number=to_number,
            carrier="telnyx",
        )
        self.sip_transport = DirectSIPTransport(
            session_id=session_id,
            caller_id=self.caller_id,
        )

    async def connect(self) -> bool:
        self.is_connected = True
        return True

    async def send_audio(self, pcm16_frame: bytes) -> None:
        """Downsample 16 kHz PCM16 to 8 kHz μ-law and emit via SIP transport."""
        await self.sip_transport.send_pcm16_frame(pcm16_frame)

    async def receive_audio(self) -> bytes | None:
        return None

    async def hangup(self) -> None:
        self.is_connected = False
        await self.sip_transport.close()

    async def health_check(self) -> bool:
        """Validate SIP transport config is present (fail-closed on bad config)."""
        if not self.caller_id.from_number or not self.caller_id.to_number:
            return False
        return bool(getattr(self.sip_transport, "session_id", None))
