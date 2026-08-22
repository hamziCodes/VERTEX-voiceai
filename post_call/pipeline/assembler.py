"""CallRecord Assembler — Constructs CallRecord from session state & FSM transition logs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.disposition import CallDisposition
from post_call.models.memory_embed import MemoryEmbedStatus
from post_call.models.recording import CallRecording


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
        compliance_tier: str = "standard",
        metrics: dict[str, Any] | None = None,
    ) -> CallRecord:
        """Construct and validate a CallRecord instance."""
        start = started_at or datetime.now(timezone.utc)
        end = ended_at or datetime.now(timezone.utc)

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

        recording = (
            CallRecording(
                recording_s3_uri=recording_uri,
                dual_channel=True,
                duration_sec=max(0.0, (end - start).total_seconds()),
            )
            if recording_uri
            else None
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
            compliance_tier=compliance_tier,
            metrics_snapshot=metrics or {},
            memory_embed_status=MemoryEmbedStatus.PENDING,
        )
