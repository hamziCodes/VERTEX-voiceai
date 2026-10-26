"""PostCallPipeline Enqueue Handler — Asynchronous post-call processing pipeline."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from core.db.repos.post_call_repo import build_post_call_repository
from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.disposition import CallDisposition
from post_call.models.policy import PostCallPolicy
from post_call.models.recording import CallRecording, RecordingState
from post_call.pipeline.recording_policy import RecordingPolicy

logger = logging.getLogger(__name__)


class PostCallPipeline:
    """Async pipeline for post-call processing, redaction, and CRM dispatch."""

    def __init__(self, repo: Any | None = None) -> None:
        self.repo = repo or build_post_call_repository()
        self.processed_records: list[CallRecord] = []

    async def start_session(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        started_at: datetime,
        transport_type: str,
        policy: PostCallPolicy,
        provider_snapshot: dict[str, Any],
        caller_id: str | None = None,
        compliance_tier: str = "standard",
    ) -> CallRecord:
        return await self.repo.start_call(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            started_at=started_at,
            transport_type=transport_type,
            policy=policy,
            provider_snapshot=provider_snapshot,
            caller_id=caller_id,
            compliance_tier=compliance_tier,
        )

    async def append_turn(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        ordinal: int,
        turn: DiarizedTurn,
    ) -> CallRecord:
        return await self.repo.append_turn(
            tenant_id=tenant_id,
            session_id=session_id,
            ordinal=ordinal,
            turn=turn,
        )

    async def finalize_session(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        ended_at: datetime,
        end_reason: str,
        disposition: CallDisposition,
        metrics_snapshot: dict[str, Any],
        usage_snapshot: dict[str, Any],
        recording_state: RecordingState,
        recording: CallRecording | None = None,
        recording_error_code: str | None = None,
    ) -> CallRecord:
        return await self.repo.finalize_call(
            tenant_id=tenant_id,
            session_id=session_id,
            ended_at=ended_at,
            end_reason=end_reason,
            disposition=disposition,
            metrics_snapshot=metrics_snapshot,
            usage_snapshot=usage_snapshot,
            recording_state=recording_state,
            recording=recording,
            recording_error_code=recording_error_code,
        )

    async def enqueue(self, record: CallRecord) -> bool:
        """Enqueue and process a CallRecord.

        Fail the persist gate when explicit policy requires a missing recording.
        """
        has_rec = record.recording_state is RecordingState.AVAILABLE
        if not RecordingPolicy.validate_record(
            record.compliance_tier, has_rec, record.policy_snapshot
        ):
            logger.error(
                "CallRecord failed compliance recording gate for tier '%s'",
                record.compliance_tier,
            )
            raise ValueError(
                f"Recording is mandatory for compliance tier '{record.compliance_tier}'"
            )

        if hasattr(self.repo, "save"):
            await self.repo.save(record)
        else:
            policy = PostCallPolicy.model_validate(record.policy_snapshot or {})
            await self.start_session(
                tenant_id=record.tenant_id,
                agent_id=record.agent_id,
                session_id=record.session_id,
                started_at=record.started_at,
                transport_type=record.transport_type,
                policy=policy,
                provider_snapshot=record.provider_snapshot,
                caller_id=record.caller_id,
                compliance_tier=record.compliance_tier,
            )
            for ordinal, turn in enumerate(record.turns):
                await self.append_turn(
                    tenant_id=record.tenant_id,
                    session_id=record.session_id,
                    ordinal=ordinal,
                    turn=turn,
                )
            if record.ended_at is not None:
                await self.finalize_session(
                    tenant_id=record.tenant_id,
                    session_id=record.session_id,
                    ended_at=record.ended_at,
                    end_reason=record.end_reason,
                    disposition=record.disposition,
                    metrics_snapshot=record.metrics_snapshot,
                    usage_snapshot=record.usage_snapshot,
                    recording_state=record.recording_state,
                    recording=record.recording,
                    recording_error_code=record.recording_error_code,
                )

        self.processed_records.append(record)
        return True
