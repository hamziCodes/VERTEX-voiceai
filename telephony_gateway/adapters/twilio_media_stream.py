"""Abstract, unimplemented Twilio Media Streams interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from telephony_gateway.base import BaseTelephonyTransport


class TwilioMediaStreamTransport(BaseTelephonyTransport, ABC):
    """Abstract interface stub for Twilio Media Streams (WebSocket μ-law stream).

    This is intentionally unimplemented in v1. DirectSIP is the primary path.
    """

    @abstractmethod
    async def process_media_event(self, event_data: dict) -> None:
        """Abstract event handler for Twilio WebSocket media frames."""
        pass
