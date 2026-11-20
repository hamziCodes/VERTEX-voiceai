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

# Tables kept on tenant erasure, and why:
# - privacy_deletion_jobs/events: the erasure job itself and its append-only
#   proof (identifiers and codes only, no content);
# - platform_audit_events, platform_support_sessions: staff accountability
#   (who accessed what and why), no customer content by construction;
# - audit_log: the tenant's security audit trail is immutable by trigger
#   (migration 006) and is retained as the record of who did what, including
#   the erasure request itself. It holds actor identifiers and actions, not
#   conversation content. Whether it must also be erased is a legal decision
#   (H14 chose no compliance claims at launch);
# - tenants: a tombstone row (name replaced, deleted_at set) so the identifier
#   cannot be reused and foreign keys stay valid;
# - schema_migrations: not tenant data.
_ERASURE_KEEP = frozenset(
    {
        "privacy_deletion_jobs",
        "privacy_deletion_events",
        "platform_audit_events",
        "platform_support_sessions",
        "audit_log",
        "tenants",
        "schema_migrations",
    }
)


class PostgresPrivacyJobRepository:
    """PostgreSQL job queue with durable per-object deletion checkpoints."""

    # Pre-Phase-14 explicit list, kept for reference; tenant erasure now
    # discovers every table with a tenant_id column (see _erasure_plan).
    _ERASURE_ROOT_TABLES = (
        "telephony_outbound_requests",
        "telephony_outbound_policies",
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
    async def _event(
        connection: Any,
        job: PrivacyDeletionJob,
        event: str,
        *,
        error_code: str | None = None,
        actor: str = "system",
        counts: dict[str, int] | None = None,
    ) -> None:
        await connection.execute(
            "INSERT INTO privacy_deletion_events "
            "(job_id, tenant_id, job_kind, call_id, event, error_code, actor, counts) "
            "VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, %s, %s, %s::jsonb)",
            (
                str(job.job_id),
                str(job.tenant_id),
                job.kind.value,
                str(job.call_id) if job.call_id else None,
                event,
                error_code[:64] if error_code else None,
                actor[:128],
                json.dumps(counts or {}),
            ),
        )

    async def record_event(
        self,
        job: PrivacyDeletionJob,
        event: str,
        *,
        counts: dict[str, int] | None = None,
    ) -> None:
        async with self.database.platform_transaction() as connection:
            await self._event(connection, job, event, counts=counts)

    async def events(self, job_id: UUID) -> list[dict[str, Any]]:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT event, error_code, actor, counts, created_at "
                "FROM privacy_deletion_events WHERE job_id = %s::uuid "
                "ORDER BY event_id",
                (str(job_id),),
            )
            rows = await cursor.fetchall()
        return [
            {
                "event": r[0],
                "error_code": r[1],
                "actor": r[2],
                "counts": r[3] or {},
                "at": r[4].isoformat(),
            }
            for r in rows
        ]

    async def get_for_tenant(self, tenant_id: UUID, job_id: UUID) -> PrivacyDeletionJob:
        job = await self.get(job_id)
        if job.tenant_id != tenant_id:
            raise KeyError(job_id)
        return job

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
        actor: str = "system",
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
                + self._select()
                + ", (xmax = 0) AS inserted",
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
            job = self._from_row(row)
            if row[-1]:
                await self._event(connection, job, "requested", actor=actor)
        return job

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
            if rows:
                await connection.execute(
                    "INSERT INTO privacy_deletion_events "
                    "(job_id, tenant_id, job_kind, call_id, event, actor) "
                    "SELECT job_id, tenant_id, job_kind, call_id, 'requested', "
                    "'retention_policy' FROM privacy_deletion_jobs "
                    "WHERE job_id = ANY(%s::uuid[])",
                    ([str(r[0]) for r in rows],),
                )
        return len(rows)

    async def request_call_deletion(
        self, tenant_id: UUID, call_id: UUID, *, actor: str
    ) -> PrivacyDeletionJob | None:
        """Queue deletion of one conversation and its recording.

        Returns ``None`` when the call does not exist for this tenant and raises
        :class:`PrivacyJobConflictError` when it is under legal hold.
        """
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT legal_hold, recording_s3_uri FROM call_records "
                "WHERE tenant_id = %s::uuid AND call_id = %s::uuid",
                (str(tenant_id), str(call_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        if row[0]:
            raise PrivacyJobConflictError("Legal hold prevents deletion.")
        return await self.enqueue(
            tenant_id=tenant_id,
            kind=PrivacyJobKind.RETENTION,
            request_key=f"erasure:call:{call_id}",
            call_id=call_id,
            object_references=(row[1],) if row[1] else (),
            actor=actor,
        )

    async def request_tenant_erasure(
        self, tenant_id: UUID, *, actor: str
    ) -> PrivacyDeletionJob:
        """Queue erasure of the whole workspace (held calls block completion)."""
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT recording_s3_uri FROM call_records WHERE tenant_id = %s::uuid "
                "AND recording_s3_uri IS NOT NULL",
                (str(tenant_id),),
            )
            references = tuple(r[0] for r in await cursor.fetchall())
        return await self.enqueue(
            tenant_id=tenant_id,
            kind=PrivacyJobKind.TENANT_ERASURE,
            request_key="erasure:tenant",
            object_references=references,
            actor=actor,
        )

    async def set_legal_hold(
        self, tenant_id: UUID, call_id: UUID, *, hold: bool, actor: str
    ) -> bool:
        """Set or release a call's legal hold; releasing requeues parked jobs."""
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "UPDATE call_records SET legal_hold = %s WHERE tenant_id = %s::uuid "
                "AND call_id = %s::uuid RETURNING call_id",
                (hold, str(tenant_id), str(call_id)),
            )
            if await cursor.fetchone() is None:
                return False
            if not hold:
                await self._release_held(connection, tenant_id, call_id, actor)
        return True

    async def _release_held(
        self, connection: Any, tenant_id: UUID, call_id: UUID, actor: str
    ) -> None:
        remaining = await connection.execute(
            "SELECT EXISTS (SELECT 1 FROM call_records WHERE tenant_id = %s::uuid "
            "AND legal_hold = TRUE)",
            (str(tenant_id),),
        )
        tenant_still_held = bool((await remaining.fetchone())[0])
        cursor = await connection.execute(
            "UPDATE privacy_deletion_jobs SET state = 'queued', available_at = NOW(), "
            "last_error_code = NULL, updated_at = NOW() "
            "WHERE tenant_id = %s::uuid AND state = 'held' AND "
            "(call_id = %s::uuid OR (call_id IS NULL AND NOT %s)) RETURNING "
            + self._select(),
            (str(tenant_id), str(call_id), tenant_still_held),
        )
        for row in await cursor.fetchall():
            await self._event(connection, self._from_row(row), "released", actor=actor)

    async def hold(
        self, job_id: UUID, *, worker_id: str, now: datetime | None = None
    ) -> PrivacyDeletionJob:
        """Park a job behind a legal hold without consuming a retry."""
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            job = await self._leased(connection, job_id, worker_id)
            cursor = await connection.execute(
                "UPDATE privacy_deletion_jobs SET state = 'held', lease_owner = NULL, "
                "lease_expires_at = NULL, last_error_code = 'legal_hold', "
                "updated_at = %s WHERE job_id = %s::uuid RETURNING " + self._select(),
                (timestamp, str(job_id)),
            )
            held = self._from_row(await cursor.fetchone())
            await self._event(connection, job, "held", error_code="legal_hold")
        return held

    @staticmethod
    async def _erasure_plan(connection: Any) -> list[str]:
        """Every public table with a tenant_id column, children before parents."""
        cursor = await connection.execute(
            "SELECT c.table_name FROM information_schema.columns c "
            "JOIN information_schema.tables t ON t.table_schema = c.table_schema "
            "AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE' "
            "WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id'"
        )
        tables = {r[0] for r in await cursor.fetchall()} - _ERASURE_KEEP
        cursor = await connection.execute(
            "SELECT DISTINCT child.relname, parent.relname FROM pg_constraint k "
            "JOIN pg_class child ON child.oid = k.conrelid "
            "JOIN pg_class parent ON parent.oid = k.confrelid "
            "WHERE k.contype = 'f' AND child.relnamespace = 'public'::regnamespace"
        )
        parents: dict[str, set[str]] = {table: set() for table in tables}
        for child, parent in await cursor.fetchall():
            if child in tables and parent in tables and child != parent:
                parents[child].add(parent)
        # Delete a table only after every table that references it.
        children: dict[str, set[str]] = {table: set() for table in tables}
        for child, refs in parents.items():
            for parent in refs:
                children[parent].add(child)
        ordered: list[str] = []
        remaining = set(tables)
        while remaining:
            ready = sorted(t for t in remaining if not (children[t] & remaining))
            if not ready:  # a cycle: fall back to a stable order; CASCADE handles it
                ready = sorted(remaining)
            ordered.extend(ready)
            remaining -= set(ready)
        return ordered

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
                deleted = await connection.execute(
                    "DELETE FROM call_records WHERE tenant_id = %s::uuid "
                    "AND call_id = %s::uuid AND legal_hold = FALSE",
                    (str(job.tenant_id), str(job.call_id)),
                )
                await self._event(
                    connection,
                    job,
                    "database_deleted",
                    counts={"call_records": deleted.rowcount or 0},
                )
            else:
                held = await connection.execute(
                    "SELECT EXISTS (SELECT 1 FROM call_records "
                    "WHERE tenant_id = %s::uuid AND legal_hold = TRUE)",
                    (str(job.tenant_id),),
                )
                if (await held.fetchone())[0]:
                    raise PrivacyJobConflictError("Legal hold prevents deletion.")
                member_cursor = await connection.execute(
                    "SELECT DISTINCT user_id FROM memberships "
                    "WHERE tenant_id = %s::uuid",
                    (str(job.tenant_id),),
                )
                member_ids = [str(r[0]) for r in await member_cursor.fetchall()]
                counts: dict[str, int] = {}
                for table in await self._erasure_plan(connection):
                    deleted = await connection.execute(
                        f'DELETE FROM "{table}" WHERE tenant_id = %s::uuid',  # noqa: S608
                        (str(job.tenant_id),),
                    )
                    if deleted.rowcount:
                        counts[table] = deleted.rowcount
                await connection.execute(
                    "DELETE FROM privacy_deletion_jobs WHERE tenant_id = %s::uuid "
                    "AND job_id <> %s::uuid",
                    (str(job.tenant_id), str(job.job_id)),
                )
                if member_ids:
                    # People whose only access was this workspace (and who are
                    # not Wavia staff) are erased with it.
                    orphans = await connection.execute(
                        "DELETE FROM users u WHERE u.id = ANY(%s::uuid[]) "
                        "AND NOT EXISTS (SELECT 1 FROM memberships m "
                        "WHERE m.user_id = u.id) "
                        "AND NOT EXISTS (SELECT 1 FROM platform_memberships p "
                        "WHERE p.user_id = u.id) "
                        "AND NOT EXISTS (SELECT 1 FROM platform_audit_events a "
                        "WHERE a.actor_user_id = u.id)",
                        (member_ids,),
                    )
                    if orphans.rowcount:
                        counts["users"] = orphans.rowcount
                await connection.execute(
                    "UPDATE tenants SET name = %s, allowed_origins = '{}', "
                    "deleted_at = NOW(), updated_at = NOW() WHERE id = %s::uuid",
                    (f"Erased tenant {str(job.tenant_id)[:8]}", str(job.tenant_id)),
                )
                await self._event(connection, job, "database_deleted", counts=counts)
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
            await self._event(connection, job, "completed")
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
            await self._event(
                connection,
                job,
                "failed" if will_retry else "dead_lettered",
                error_code=error_code,
            )
        return self._from_row(row)
