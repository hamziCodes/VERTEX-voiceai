"""Construct call records from session state and transition logs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.disposition import CallDisposition
from post_call.models.memory_embed import MemoryEmbedStatus
from post_call.models.recording import CallRecording, RecordingState


class CallRecordAssembler:
    """Assembles a full CallRecord from session turn history & FSM logs."""

    @staticmethod
    def assemble(
        tenant_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        turns_data: list[dict[str, Any]],
        caller_id: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        end_reason: str = "user_hangup",
        transport_type: str = "websocket",
        recording_uri: str | None = None,
        recording_checksum: str | None = None,
        recording_channel_count: int = 1,
        recording_storage_region: str | None = None,
        compliance_tier: str = "standard",
        metrics: dict[str, Any] | None = None,
    ) -> CallRecord:
        """Construct and validate a CallRecord instance."""
        start = started_at or datetime.now(UTC)
        end = ended_at or datetime.now(UTC)

        turns: list[DiarizedTurn] = []
        for t in turns_data:
            turns.append(
                DiarizedTurn(
                    speaker=t.get("speaker", "user"),
                    text=t.get("text", ""),
                    start_ms=t.get("start_ms", 0),
                    end_ms=t.get("end_ms", 0),
                    language=t.get("language", "en"),
                    confidence=t.get("confidence", 1.0),
                )
            )

        # Zero-retention & GDPR strict compliance handling (FIX-018)
        tier_lower = compliance_tier.lower().strip()
        if tier_lower in ("gdpr_strict", "zero_retention"):
            # Suppress audio recording storage URI for zero-retention compliance
            recording_uri = None

        recording = None
        if recording_uri:
            if not recording_checksum or not recording_storage_region:
                raise ValueError(
                    "Recording URI requires checksum and storage-region evidence."
                )
            recording = CallRecording(
                state=RecordingState.AVAILABLE,
                recording_s3_uri=recording_uri,
                checksum=recording_checksum,
                channel_count=recording_channel_count,
                dual_channel=recording_channel_count == 2,
                duration_sec=max(0.001, (end - start).total_seconds()),
                storage_region=recording_storage_region,
            )

        return CallRecord(
            call_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            caller_id=caller_id,
            started_at=start,
            ended_at=end,
            end_reason=end_reason,
            transport_type=transport_type,
            disposition=CallDisposition.COMPLETED,
            turns=turns,
            recording=recording,
            recording_state=(
                RecordingState.AVAILABLE
                if recording is not None
                else RecordingState.NOT_REQUESTED
            ),
            compliance_tier=compliance_tier,
            metrics_snapshot=metrics or {},
            memory_embed_status=MemoryEmbedStatus.PENDING,
        )
