"""Durable restart-safe privacy deletion repository."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from core.compliance.privacy_jobs import (
    PrivacyDeletionJob,
    PrivacyJobConflictError,
    PrivacyJobKind,
    PrivacyJobState,
)
from core.db.async_pg import AsyncDatabase, get_default_database


class PostgresPrivacyJobRepository:
    """PostgreSQL job queue with durable per-object deletion checkpoints."""

    _ERASURE_ROOT_TABLES = (
        "post_call_webhook_targets",
        "webhook_targets",
        "knowledge_bases",
        "mcp_servers",
        "telephony_commands",
        "telephony_events",
        "telephony_calls",
        "agent_configs",
        "agents",
        "tenant_credentials",
        "usage_events",
        "quota_state",
        "telephony_dids",
        "sip_trunks",
        "extraction_schemas",
        "dead_letter_queue",
        "tenant_compliance_profile",
        "erasure_requests",
        "memberships",
        "api_keys",
        "mint_rejections",
    )

    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    @staticmethod
    def _select() -> str:
        return (
            "job_id, tenant_id, job_kind, request_key, call_id, object_refs, "
            "completed_object_refs, database_deleted, state, attempt_count, "
            "max_attempts, available_at, lease_owner, lease_expires_at, "
            "last_error_code, created_at, updated_at"
        )

    @staticmethod
    def _from_row(row: Any) -> PrivacyDeletionJob:
        return PrivacyDeletionJob(
            job_id=row[0],
            tenant_id=row[1],
            kind=PrivacyJobKind(row[2]),
            request_key=row[3],
            call_id=row[4],
            object_references=tuple(row[5] or ()),
            completed_object_references=tuple(row[6] or ()),
            database_deleted=row[7],
            state=PrivacyJobState(row[8]),
            attempt_count=row[9],
            max_attempts=row[10],
            available_at=row[11],
            lease_owner=row[12],
            lease_expires_at=row[13],
            last_error_code=row[14],
            created_at=row[15],
            updated_at=row[16],
        )

    async def enqueue(
        self,
        *,
        tenant_id: UUID,
        kind: PrivacyJobKind,
        request_key: str,
        call_id: UUID | None = None,
        object_references: tuple[str, ...] = (),
        max_attempts: int = 5,
        now: datetime | None = None,
    ) -> PrivacyDeletionJob:
        if not request_key.strip():
            raise ValueError("request_key is required.")
        if kind is PrivacyJobKind.RETENTION and call_id is None:
            raise ValueError("Retention deletion requires call_id.")
        timestamp = now or datetime.now(UTC)
        refs = tuple(dict.fromkeys(item for item in object_references if item))
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "INSERT INTO privacy_deletion_jobs "
                "(job_id, tenant_id, job_kind, request_key, call_id, object_refs, "
                "max_attempts, available_at, created_at, updated_at) VALUES "
                "(%s::uuid, %s::uuid, %s, %s, %s::uuid, %s::jsonb, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, request_key) DO UPDATE SET "
                "updated_at = privacy_deletion_jobs.updated_at RETURNING "
                + self._select(),
                (
                    str(uuid4()),
                    str(tenant_id),
                    kind.value,
                    request_key,
                    str(call_id) if call_id else None,
                    json.dumps(refs),
                    max_attempts,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            row = await cursor.fetchone()
        return self._from_row(row)

    async def enqueue_due_retention(
        self, *, now: datetime | None = None, limit: int = 100
    ) -> int:
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "INSERT INTO privacy_deletion_jobs "
                "(tenant_id, job_kind, request_key, call_id, object_refs, "
                "available_at) SELECT tenant_id, 'retention', "
                "'retention:' || call_id::text, call_id, "
                "CASE WHEN recording_s3_uri IS NULL THEN '[]'::jsonb "
                "ELSE jsonb_build_array(recording_s3_uri) END, %s "
                "FROM call_records WHERE finalized_at IS NOT NULL "
                "AND purge_after <= %s AND legal_hold = FALSE "
                "ORDER BY purge_after LIMIT %s "
                "ON CONFLICT (tenant_id, request_key) DO NOTHING RETURNING job_id",
                (timestamp, timestamp, max(1, min(limit, 1000))),
            )
            rows = await cursor.fetchall()
        return len(rows)

    async def get(self, job_id: UUID) -> PrivacyDeletionJob:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._select()
                + " FROM privacy_deletion_jobs WHERE job_id = %s::uuid",
                (str(job_id),),
            )
            row = await cursor.fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._from_row(row)

    async def claim_next(
        self, worker_id: str, *, now: datetime | None = None, lease_seconds: int = 60
    ) -> PrivacyDeletionJob | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        timestamp = now or datetime.now(UTC)
        lease_expires = timestamp + timedelta(seconds=max(1, lease_seconds))
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT job_id FROM privacy_deletion_jobs "
                "WHERE attempt_count < max_attempts AND "
                "(((state IN ('queued', 'retry_wait')) AND available_at <= %s) OR "
                "(state = 'running' AND lease_expires_at <= %s)) "
                "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1",
                (timestamp, timestamp),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            updated = await connection.execute(
                "UPDATE privacy_deletion_jobs SET state = 'running', lease_owner = %s, "
                "lease_expires_at = %s, updated_at = %s WHERE job_id = %s::uuid "
                "RETURNING " + self._select(),
                (worker_id, lease_expires, timestamp, str(row[0])),
            )
            claimed = await updated.fetchone()
        return self._from_row(claimed)

    async def is_legal_hold(self, job: PrivacyDeletionJob) -> bool:
        async with self.database.platform_transaction() as connection:
            if job.call_id is not None:
                cursor = await connection.execute(
                    "SELECT legal_hold FROM call_records WHERE tenant_id = %s::uuid "
                    "AND call_id = %s::uuid",
                    (str(job.tenant_id), str(job.call_id)),
                )
            else:
                cursor = await connection.execute(
                    "SELECT EXISTS (SELECT 1 FROM call_records "
                    "WHERE tenant_id = %s::uuid "
                    "AND legal_hold = TRUE)",
                    (str(job.tenant_id),),
                )
            row = await cursor.fetchone()
        return bool(row and row[0])

    async def _leased(
        self, connection: Any, job_id: UUID, worker_id: str
    ) -> PrivacyDeletionJob:
        cursor = await connection.execute(
            "SELECT "
            + self._select()
            + " FROM privacy_deletion_jobs WHERE job_id = %s::uuid FOR UPDATE",
            (str(job_id),),
        )
        row = await cursor.fetchone()
        if row is None:
            raise KeyError(job_id)
        job = self._from_row(row)
        if job.state is not PrivacyJobState.RUNNING or job.lease_owner != worker_id:
            raise PrivacyJobConflictError("Privacy job lease is not owned by worker.")
        return job

    async def mark_object_deleted(
        self, job_id: UUID, *, worker_id: str, reference: str
    ) -> PrivacyDeletionJob:
        async with self.database.platform_transaction() as connection:
            job = await self._leased(connection, job_id, worker_id)
            completed = tuple(
                dict.fromkeys((*job.completed_object_references, reference))
            )
            cursor = await connection.execute(
                "UPDATE privacy_deletion_jobs SET completed_object_refs = %s::jsonb, "
                "updated_at = NOW() WHERE job_id = %s::uuid RETURNING "
                + self._select(),
                (json.dumps(completed), str(job_id)),
            )
            row = await cursor.fetchone()
        return self._from_row(row)

    async def delete_database_data(
        self, job_id: UUID, *, worker_id: str
    ) -> PrivacyDeletionJob:
        async with self.database.platform_transaction() as connection:
            job = await self._leased(connection, job_id, worker_id)
            if job.call_id is not None:
                held = await connection.execute(
                    "SELECT legal_hold FROM call_records WHERE tenant_id = %s::uuid "
                    "AND call_id = %s::uuid FOR UPDATE",
                    (str(job.tenant_id), str(job.call_id)),
                )
                row = await held.fetchone()
                if row and row[0]:
                    raise PrivacyJobConflictError("Legal hold prevents deletion.")
                await connection.execute(
                    "DELETE FROM call_records WHERE tenant_id = %s::uuid "
                    "AND call_id = %s::uuid AND legal_hold = FALSE",
                    (str(job.tenant_id), str(job.call_id)),
                )
            else:
                held = await connection.execute(
                    "SELECT EXISTS (SELECT 1 FROM call_records "
                    "WHERE tenant_id = %s::uuid AND legal_hold = TRUE)",
                    (str(job.tenant_id),),
                )
                if (await held.fetchone())[0]:
                    raise PrivacyJobConflictError("Legal hold prevents deletion.")
                for table in self._ERASURE_ROOT_TABLES:
                    await connection.execute(
                        f"DELETE FROM {table} WHERE tenant_id = %s::uuid",  # noqa: S608
                        (str(job.tenant_id),),
                    )
                await connection.execute(
                    "DELETE FROM privacy_deletion_jobs WHERE tenant_id = %s::uuid "
                    "AND job_id <> %s::uuid",
                    (str(job.tenant_id), str(job.job_id)),
                )
                await connection.execute(
                    "UPDATE tenants SET name = %s, allowed_origins = '{}', "
                    "deleted_at = NOW(), updated_at = NOW() WHERE id = %s::uuid",
                    (f"Erased tenant {str(job.tenant_id)[:8]}", str(job.tenant_id)),
                )
            cursor = await connection.execute(
                "UPDATE privacy_deletion_jobs SET database_deleted = TRUE, "
                "updated_at = NOW() WHERE job_id = %s::uuid RETURNING "
                + self._select(),
                (str(job_id),),
            )
            row = await cursor.fetchone()
        return self._from_row(row)

    async def complete(
        self, job_id: UUID, *, worker_id: str, now: datetime | None = None
    ) -> PrivacyDeletionJob:
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            job = await self._leased(connection, job_id, worker_id)
            if set(job.completed_object_references) != set(job.object_references):
                raise PrivacyJobConflictError(
                    "Recording deletion checkpoint is incomplete."
                )
            if not job.database_deleted:
                raise PrivacyJobConflictError(
                    "Database deletion checkpoint is incomplete."
                )
            cursor = await connection.execute(
                "UPDATE privacy_deletion_jobs SET state = 'succeeded', "
                "lease_owner = NULL, lease_expires_at = NULL, last_error_code = NULL, "
                "updated_at = %s WHERE job_id = %s::uuid RETURNING " + self._select(),
                (timestamp, str(job_id)),
            )
            row = await cursor.fetchone()
        return self._from_row(row)

    async def fail(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        error_code: str,
        retryable: bool = True,
        now: datetime | None = None,
    ) -> PrivacyDeletionJob:
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            job = await self._leased(connection, job_id, worker_id)
            attempt = job.attempt_count + 1
            will_retry = retryable and attempt < job.max_attempts
            state = (
                PrivacyJobState.RETRY_WAIT
                if will_retry
                else PrivacyJobState.DEAD_LETTER
            )
            available = (
                timestamp + timedelta(seconds=min(300, 2 ** (attempt - 1)))
                if will_retry
                else timestamp
            )
            cursor = await connection.execute(
                "UPDATE privacy_deletion_jobs SET state = %s, attempt_count = %s, "
                "available_at = %s, lease_owner = NULL, lease_expires_at = NULL, "
                "last_error_code = %s, updated_at = %s WHERE job_id = %s::uuid "
                "RETURNING " + self._select(),
                (
                    state.value,
                    attempt,
                    available,
                    error_code[:64],
                    timestamp,
                    str(job_id),
                ),
            )
            row = await cursor.fetchone()
        return self._from_row(row)
