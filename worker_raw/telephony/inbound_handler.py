"""Inbound Telephony Session Handler — Connects DirectSIPTransport to PipelineOrchestrator."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from core.transport.caller_id import CallerIdContext
from core.transport.direct_sip import DirectSIPTransport
from telephony_gateway.transcoding.mulaw import mulaw_to_pcm16


class InboundTelephonySessionHandler:
    """Manages lifecycle of an inbound telephony session via DirectSIP."""

    def __init__(
        self,
        session_id: UUID,
        tenant_id: UUID,
        agent_id: UUID,
        caller_id: CallerIdContext,
    ) -> None:
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.caller_id = caller_id
        self.transport = DirectSIPTransport(session_id=session_id, caller_id=caller_id)
        self.start_time = time.time()
        self.duration_sec = 0.0

    async def handle_inbound_audio(self, mulaw_payload: bytes) -> list[bytes]:
        """Ingest μ-law RTP payload and return 16kHz PCM16 canonical frames for pipeline."""
        return await self.transport.receive_mulaw_frame(mulaw_payload)

    async def close(self) -> float:
        """Close session and return call duration in seconds for telemetry/metering."""
        await self.transport.close()
        self.duration_sec = max(0.0, time.time() - self.start_time)
        return self.duration_sec
