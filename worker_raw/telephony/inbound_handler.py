"""Public Telnyx handler with a frozen offline DirectSIP compatibility mode."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from core.metering.kinds import TELEPHONY_SEC
from core.metering.usage_meter import UsageMeter
from core.transport.caller_id import CallerIdContext
from core.transport.direct_sip import DirectSIPTransport
from core.types.audio import AudioFrame
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.telephony.session_supervisor import TelephonySessionSupervisor


class InboundTelephonySessionHandler:
    """Use the Telnyx supervisor in production; retain Phase 18 codec tests."""

    def __init__(
        self,
        *,
        session_id: UUID | None = None,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        caller_id: CallerIdContext,
        orchestrator: PipelineOrchestrator | None = None,
        meter: UsageMeter | None = None,
        **supervisor_kwargs: Any,
    ) -> None:
        self._supervisor: TelephonySessionSupervisor | None = None
        self.transport: DirectSIPTransport | None = None
        if supervisor_kwargs:
            self._supervisor = TelephonySessionSupervisor(
                caller_id=caller_id,
                orchestrator=orchestrator or PipelineOrchestrator(),
                usage_meter=meter,
                **supervisor_kwargs,
            )
            self._legacy_codec_mode = False
            self.orchestrator = self._supervisor.orchestrator
            self.usage_meter = self._supervisor.usage_meter
            return
        if session_id is None or tenant_id is None or agent_id is None:
            raise ValueError("production Telnyx sessions require supervisor arguments")
        self._legacy_codec_mode = True
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.caller_id = caller_id
        self.transport = DirectSIPTransport(session_id=session_id, caller_id=caller_id)
        self.orchestrator = orchestrator or PipelineOrchestrator()
        self.usage_meter = meter or UsageMeter()
        self._legacy_started_at = time.monotonic()

    async def run(
        self,
        *,
        signature_header: str | None,
        timestamp_header: str | None,
        now: float | None = None,
    ) -> None:
        if self._supervisor is None:
            raise RuntimeError("offline compatibility mode cannot run carrier media")
        await self._supervisor.run(
            signature_header=signature_header,
            timestamp_header=timestamp_header,
            now=now,
        )

    async def wait_ready(self, timeout: float = 2.0) -> None:
        if self._supervisor is None:
            raise RuntimeError("offline compatibility mode has no carrier readiness")
        await self._supervisor.wait_ready(timeout)

    async def stop(self, reason: str = "worker_shutdown") -> None:
        if self._supervisor is None:
            await self.close()
            return
        await self._supervisor.stop(reason)

    async def handle_inbound_audio(self, mulaw_payload: bytes) -> list[bytes]:
        """Exercise the frozen codec/rebuffer primitive; no SIP network is opened."""
        if not self._legacy_codec_mode:
            raise RuntimeError(
                "production Telnyx sessions ingest through the media adapter"
            )
        assert self.transport is not None
        pcm_chunks = await self.transport.receive_mulaw_frame(mulaw_payload)
        for chunk in pcm_chunks:
            await self.orchestrator.process_frame_async(
                AudioFrame(pcm16=chunk, sample_rate=16000, channel_count=1)
            )
        return pcm_chunks

    async def close(self) -> float:
        """Close only the frozen offline compatibility transport."""
        if not self._legacy_codec_mode:
            await self.stop("application_close")
            return 0.0
        assert self.transport is not None
        await self.transport.close()
        duration = max(0.0, time.monotonic() - self._legacy_started_at)
        if duration > 0:
            await self.usage_meter.arecord(
                str(self.tenant_id),
                str(self.session_id),
                TELEPHONY_SEC,
                duration,
                event_key=f"{self.session_id}:telephony_sec:final",
                unit="seconds",
            )
        await self.orchestrator.shutdown_runtime_resources()
        return duration
