"""Tenant-scoped call lifecycle and incremental transcript repositories."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from core.db.async_pg import AsyncDatabase, get_default_database
from core.db.pg import use_memory_repos
from post_call.jobs.models import PostCallIntelligenceResult, PostCallJob
from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.disposition import CallDisposition
from post_call.models.policy import PostCallPolicy
from post_call.models.recording import CallRecording, RecordingState
from post_call.review.models import ReviewRequest


class PostCallNotFoundError(LookupError):
    pass


class PostCallConflictError(RuntimeError):
    pass


class InMemoryPostCallRepository:
    """Deterministic local repository with production-equivalent invariants."""

    def __init__(self) -> None:
        self._calls: dict[tuple[UUID, UUID], CallRecord] = {}
        self._turns: dict[tuple[UUID, UUID], dict[int, DiarizedTurn]] = {}
        self._post_call_jobs: dict[UUID, PostCallJob] = {}
        self._post_call_results: dict[
            tuple[UUID, UUID], PostCallIntelligenceResult
        ] = {}
        self._post_call_reviews: dict[UUID, ReviewRequest] = {}

    async def start_call(
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
        intelligence_config_snapshot: dict[str, Any] | None = None,
    ) -> CallRecord:
        key = (tenant_id, session_id)
        existing = self._calls.get(key)
        if existing is not None:
            return existing.model_copy(deep=True)
        record = CallRecord(
            call_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            caller_id=caller_id,
            started_at=started_at,
            ended_at=None,
            transport_type=transport_type,
            compliance_tier=compliance_tier,
            policy_snapshot=policy.model_dump(mode="json"),
            provider_snapshot=dict(provider_snapshot),
            intelligence_config_snapshot=dict(intelligence_config_snapshot or {}),
        )
        self._calls[key] = record
        self._turns[key] = {}
        return record.model_copy(deep=True)

    async def get_call(self, tenant_id: UUID, session_id: UUID) -> CallRecord:
        key = (tenant_id, session_id)
        record = self._calls.get(key)
        if record is None:
            raise PostCallNotFoundError("Call record not found.")
        return record.model_copy(deep=True)

    async def get_call_by_id(self, tenant_id: UUID, call_id: UUID) -> CallRecord:
        for (owner, _session_id), record in self._calls.items():
            if owner == tenant_id and record.call_id == call_id:
                return record.model_copy(deep=True)
        raise PostCallNotFoundError("Call record not found.")

    async def append_turn(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        ordinal: int,
        turn: DiarizedTurn,
    ) -> CallRecord:
        if ordinal < 0:
            raise ValueError("Turn ordinal must be non-negative.")
        key = (tenant_id, session_id)
        record = self._calls.get(key)
        if record is None:
            raise PostCallNotFoundError("Call record not found.")
        existing = self._turns[key].get(ordinal)
        if existing is not None and existing != turn:
            raise PostCallConflictError("Turn ordinal already has different content.")
        self._turns[key][ordinal] = turn
        record.turns = [self._turns[key][index] for index in sorted(self._turns[key])]
        return record.model_copy(deep=True)

    async def set_recording_state(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        state: RecordingState,
        recording: CallRecording | None = None,
        error_code: str | None = None,
    ) -> CallRecord:
        key = (tenant_id, session_id)
        record = self._calls.get(key)
        if record is None:
            raise PostCallNotFoundError("Call record not found.")
        policy = PostCallPolicy.model_validate(record.policy_snapshot)
        if state is RecordingState.RECORDING and not (
            policy.recording_enabled and policy.recording_consent_obtained
        ):
            raise PostCallConflictError("Recording requires enablement and consent.")
        if state is RecordingState.AVAILABLE:
            if recording is None:
                raise PostCallConflictError("Available recording requires evidence.")
            if recording.storage_region != policy.storage_region:
                raise PostCallConflictError("Recording region does not match policy.")
        elif recording is not None:
            raise PostCallConflictError(
                "Only available recordings may include evidence."
            )
        if state is RecordingState.FAILED and not error_code:
            raise PostCallConflictError("Failed recording requires an error code.")
        if state is not RecordingState.FAILED and error_code is not None:
            raise PostCallConflictError(
                "Only failed recordings may include an error code."
            )
        record.recording_state = state
        record.recording = recording
        record.recording_error_code = error_code
        return record.model_copy(deep=True)

    async def finalize_call(
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
        key = (tenant_id, session_id)
        record = self._calls.get(key)
        if record is None:
            raise PostCallNotFoundError("Call record not found.")
        if record.ended_at is not None:
            return record.model_copy(deep=True)
        await self.set_recording_state(
            tenant_id=tenant_id,
            session_id=session_id,
            state=recording_state,
            recording=recording,
            error_code=recording_error_code,
        )
        record.ended_at = max(ended_at, record.started_at)
        record.end_reason = end_reason[:64]
        record.disposition = disposition
        record.metrics_snapshot = dict(metrics_snapshot)
        record.usage_snapshot = dict(usage_snapshot)
        if not any(
            job.tenant_id == tenant_id and job.call_id == record.call_id
            for job in self._post_call_jobs.values()
        ):
            job = PostCallJob(
                tenant_id=tenant_id,
                call_id=record.call_id,
                payload=dict(record.intelligence_config_snapshot),
                available_at=record.ended_at,
                created_at=record.ended_at,
                updated_at=record.ended_at,
            )
            self._post_call_jobs[job.job_id] = job
        return record.model_copy(deep=True)


class PostgresPostCallRepository:
    """Psycopg implementation using the Phase 09 tenant transaction boundary."""

    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def start_call(
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
        intelligence_config_snapshot: dict[str, Any] | None = None,
    ) -> CallRecord:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "INSERT INTO call_records (call_id, tenant_id, agent_id, session_id, "
                "caller_id, started_at, ended_at, transport_type, compliance_tier, "
                "recording_state, policy_snapshot, provider_snapshot, "
                "intelligence_config_snapshot) "
                "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, NULL, %s, %s, "
                "'not_requested', %s::jsonb, %s::jsonb, %s::jsonb) "
                "ON CONFLICT (tenant_id, session_id) DO UPDATE SET updated_at = "
                "call_records.updated_at RETURNING call_id",
                (
                    str(uuid4()),
                    str(tenant_id),
                    str(agent_id),
                    str(session_id),
                    caller_id,
                    started_at,
                    transport_type,
                    compliance_tier,
                    json.dumps(policy.model_dump(mode="json")),
                    json.dumps(provider_snapshot),
                    json.dumps(intelligence_config_snapshot or {}),
                ),
            )
            row = await cursor.fetchone()
        return await self.get_call(tenant_id, session_id, call_id=row[0])

    async def get_call(
        self, tenant_id: UUID, session_id: UUID, *, call_id: UUID | None = None
    ) -> CallRecord:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT call_id, agent_id, caller_id, started_at, ended_at, "
                "end_reason, "
                "transport_type, disposition, recording_state, recording_s3_uri, "
                "dual_channel, recording_checksum, recording_channel_count, "
                "recording_duration_seconds, recording_storage_region, "
                "compliance_tier, metrics_snapshot, policy_snapshot, "
                "provider_snapshot, "
                "usage_snapshot, recording_error_code, intelligence_config_snapshot "
                "FROM call_records WHERE tenant_id = %s::uuid "
                "AND session_id = %s::uuid",
                (str(tenant_id), str(session_id)),
            )
            row = await cursor.fetchone()
            if row is None:
                raise PostCallNotFoundError("Call record not found.")
            turn_cursor = await connection.execute(
                "SELECT turn_jsonb FROM call_record_turns WHERE tenant_id = %s::uuid "
                "AND session_id = %s::uuid ORDER BY ordinal",
                (str(tenant_id), str(session_id)),
            )
            turn_rows = await turn_cursor.fetchall()
        recording_state = RecordingState(row[8])
        recording = None
        if recording_state is RecordingState.AVAILABLE:
            recording = CallRecording(
                recording_s3_uri=row[9],
                dual_channel=row[10],
                checksum=row[11],
                channel_count=row[12],
                duration_sec=row[13],
                storage_region=row[14],
            )
        return CallRecord(
            call_id=call_id or row[0],
            tenant_id=tenant_id,
            agent_id=row[1],
            session_id=session_id,
            caller_id=row[2],
            started_at=row[3],
            ended_at=row[4],
            end_reason=row[5],
            transport_type=row[6],
            disposition=CallDisposition(row[7]),
            recording_state=recording_state,
            recording=recording,
            compliance_tier=row[15],
            turns=[DiarizedTurn.model_validate(item[0]) for item in turn_rows],
            metrics_snapshot=row[16] or {},
            policy_snapshot=row[17] or {},
            provider_snapshot=row[18] or {},
            usage_snapshot=row[19] or {},
            recording_error_code=row[20],
            intelligence_config_snapshot=row[21] or {},
        )

    async def get_call_by_id(self, tenant_id: UUID, call_id: UUID) -> CallRecord:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT session_id FROM call_records WHERE tenant_id = %s::uuid "
                "AND call_id = %s::uuid",
                (str(tenant_id), str(call_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            raise PostCallNotFoundError("Call record not found.")
        return await self.get_call(tenant_id, row[0], call_id=call_id)

    async def append_turn(
        self, *, tenant_id: UUID, session_id: UUID, ordinal: int, turn: DiarizedTurn
    ) -> CallRecord:
        if ordinal < 0:
            raise ValueError("Turn ordinal must be non-negative.")
        payload = json.dumps(turn.model_dump(mode="json"), separators=(",", ":"))
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "INSERT INTO call_record_turns "
                "(tenant_id, session_id, ordinal, turn_jsonb) "
                "VALUES (%s::uuid, %s::uuid, %s, %s::jsonb) "
                "ON CONFLICT (tenant_id, session_id, ordinal) "
                "DO NOTHING RETURNING ordinal",
                (str(tenant_id), str(session_id), ordinal, payload),
            )
            inserted = await cursor.fetchone()
            if inserted is None:
                current = await connection.execute(
                    "SELECT turn_jsonb FROM call_record_turns "
                    "WHERE tenant_id = %s::uuid "
                    "AND session_id = %s::uuid AND ordinal = %s",
                    (str(tenant_id), str(session_id), ordinal),
                )
                row = await current.fetchone()
                if row is None:
                    raise PostCallNotFoundError("Call record not found.")
                if DiarizedTurn.model_validate(row[0]) != turn:
                    raise PostCallConflictError(
                        "Turn ordinal already has different content."
                    )
        return await self.get_call(tenant_id, session_id)

    async def finalize_call(
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
        current = await self.get_call(tenant_id, session_id)
        if current.ended_at is not None:
            return current
        policy = PostCallPolicy.model_validate(current.policy_snapshot)
        if recording_state is RecordingState.AVAILABLE and recording is None:
            raise PostCallConflictError("Available recording requires evidence.")
        if recording is not None and recording_state is not RecordingState.AVAILABLE:
            raise PostCallConflictError(
                "Only available recordings may include evidence."
            )
        if recording_state in {
            RecordingState.RECORDING,
            RecordingState.AVAILABLE,
        } and not (policy.recording_enabled and policy.recording_consent_obtained):
            raise PostCallConflictError("Recording requires enablement and consent.")
        if recording is not None and recording.storage_region != policy.storage_region:
            raise PostCallConflictError("Recording region does not match policy.")
        if recording_state is RecordingState.FAILED and not recording_error_code:
            raise PostCallConflictError("Failed recording requires an error code.")
        if (
            recording_state is not RecordingState.FAILED
            and recording_error_code is not None
        ):
            raise PostCallConflictError(
                "Only failed recordings may include an error code."
            )
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            updated = await connection.execute(
                "UPDATE call_records SET ended_at = GREATEST(%s, started_at), "
                "end_reason = %s, disposition = %s, metrics_snapshot = %s::jsonb, "
                "usage_snapshot = %s::jsonb, recording_state = %s, "
                "recording_s3_uri = %s, dual_channel = %s, recording_checksum = %s, "
                "recording_channel_count = %s, recording_duration_seconds = %s, "
                "recording_storage_region = %s, recording_error_code = %s, "
                "purge_after = GREATEST(%s, started_at) + make_interval(days => %s), "
                "finalized_at = NOW(), updated_at = NOW() "
                "WHERE tenant_id = %s::uuid AND session_id = %s::uuid "
                "AND ended_at IS NULL",
                (
                    ended_at,
                    end_reason[:64],
                    disposition.value,
                    json.dumps(metrics_snapshot),
                    json.dumps(usage_snapshot),
                    recording_state.value,
                    recording.recording_s3_uri if recording else None,
                    recording.dual_channel if recording else False,
                    recording.checksum if recording else None,
                    recording.channel_count if recording else None,
                    recording.duration_sec if recording else None,
                    recording.storage_region if recording else None,
                    recording_error_code,
                    ended_at,
                    policy.transcript_retention_days,
                    str(tenant_id),
                    str(session_id),
                ),
            )
            if updated.rowcount:
                await connection.execute(
                    "INSERT INTO post_call_jobs "
                    "(tenant_id, call_id, payload_jsonb, available_at) "
                    "VALUES (%s::uuid, %s::uuid, %s::jsonb, GREATEST(%s, %s)) "
                    "ON CONFLICT (tenant_id, call_id, job_type) DO NOTHING",
                    (
                        str(tenant_id),
                        str(current.call_id),
                        json.dumps(current.intelligence_config_snapshot),
                        ended_at,
                        current.started_at,
                    ),
                )
        return await self.get_call(tenant_id, session_id)


def build_post_call_repository() -> (
    InMemoryPostCallRepository | PostgresPostCallRepository
):
    """Select memory only for local/test; protected runtimes require PostgreSQL."""

    if use_memory_repos():
        return InMemoryPostCallRepository()
    return PostgresPostCallRepository()
