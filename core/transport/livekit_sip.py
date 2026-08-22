"""Optional LiveKit SIP Transport Adapter (Disabled by default; Sovereign Direct SIP is primary)."""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from core.transport.caller_id import CallerIdContext


class LiveKitSIPTransport:
    """Optional LiveKit SIP Participant Adapter — Feature-flagged convenience layer."""

    def __init__(self, session_id: UUID, caller_id: CallerIdContext) -> None:
        self.session_id = session_id
        self.caller_id = caller_id
        self.enabled = os.getenv("UCVE_ENABLE_LIVEKIT_SIP", "false").lower() == "true"
        self.room_name = f"sip-{session_id}"

    async def connect(self) -> bool:
        """Connect to LiveKit SIP room if feature flag is enabled."""
        if not self.enabled:
            # Skipped when feature flag is false (default)
            return False
        return True
