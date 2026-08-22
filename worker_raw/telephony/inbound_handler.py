"""Inbound Telephony Session Handler — Connects DirectSIPTransport to PipelineOrchestrator."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from core.types.audio import AudioFrame
from core.metering.kinds import TELEPHONY_SEC
from core.metering.usage_meter import UsageMeter
from core.transport.caller_id import CallerIdContext
from core.transport.direct_sip import DirectSIPTransport
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


class InboundTelephonySessionHandler:
    """Manages lifecycle of an inbound telephony session via DirectSIP."""

    def __init__(
        self,
        session_id: UUID,
        tenant_id: UUID,
        agent_id: UUID,
        caller_id: CallerIdContext,
        orchestrator: PipelineOrchestrator | None = None,
        meter: UsageMeter | None = None,
    ) -> None:
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.caller_id = caller_id
        self.transport = DirectSIPTransport(session_id=session_id, caller_id=caller_id)
        self.meter = meter or UsageMeter()

        self.config = PipelineSessionConfig(
            session_id=str(session_id),
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            transport_type="sip",
            caller_id=caller_id,
        )
        self.orchestrator = orchestrator or PipelineOrchestrator()
        self.start_time = time.time()
        self.duration_sec = 0.0

    async def handle_inbound_audio(self, mulaw_payload: bytes) -> list[bytes]:
        """Ingest μ-law RTP payload, wrap as AudioFrame, and feed to PipelineOrchestrator."""
        pcm_chunks = await self.transport.receive_mulaw_frame(mulaw_payload)
        for chunk in pcm_chunks:
            frame = AudioFrame(
                sample_rate=16000,
                num_channels=1,
                pcm_data=chunk,
                pts_us=int(time.time() * 1e6),
            )
            await self.orchestrator.process_frame(frame)
        return pcm_chunks

    async def close(self) -> float:
        """Close session, record TELEPHONY_SEC metering, and return call duration in seconds."""
        await self.transport.close()
        self.duration_sec = max(0.0, time.time() - self.start_time)
        if self.duration_sec > 0:
            self.meter.record(
                session_config.tenant_id if 'session_config' in locals() else str(self.tenant_id),
                str(self.session_id),
                TELEPHONY_SEC,
                int(self.duration_sec),
            )
        return self.duration_sec
