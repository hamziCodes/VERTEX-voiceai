"""Connect DirectSIPTransport to the voice pipeline."""

from __future__ import annotations

import time
from uuid import UUID

from core.metering.kinds import TELEPHONY_SEC
from core.metering.usage_meter import UsageMeter
from core.transport.caller_id import CallerIdContext
from core.transport.direct_sip import DirectSIPTransport
from core.types.audio import AudioFrame
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
        self.orchestrator = orchestrator or PipelineOrchestrator(
            on_audio_out=self._send_outbound_audio,
        )
        self.start_time = time.time()
        self.duration_sec = 0.0

    async def _send_outbound_audio(self, pcm_bytes: bytes) -> None:
        """Encode pipeline TTS egress for the DirectSIP transport."""
        await self.transport.send_pcm16_frame(pcm_bytes)

    async def handle_inbound_audio(self, mulaw_payload: bytes) -> list[bytes]:
        """Ingest an RTP payload and feed canonical audio into the pipeline."""
        pcm_chunks = await self.transport.receive_mulaw_frame(mulaw_payload)
        for chunk in pcm_chunks:
            frame = AudioFrame(
                pcm16=chunk,
                sample_rate=16000,
                timestamp_ms=time.time() * 1000.0,
                channel_count=1,
            )
            await self.orchestrator.process_frame_async(frame)
        return pcm_chunks

    async def close(self) -> float:
        """Close the session and meter its telephony duration."""
        await self.transport.close()
        self.duration_sec = max(0.0, time.time() - self.start_time)
        if self.duration_sec > 0:
            await self.meter.arecord(
                str(self.tenant_id),
                str(self.session_id),
                TELEPHONY_SEC,
                self.duration_sec,
                event_key=f"{self.session_id}:telephony_sec:final",
                unit="seconds",
            )
        return self.duration_sec
