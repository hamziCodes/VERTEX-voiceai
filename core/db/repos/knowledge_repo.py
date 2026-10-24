"""Tenant-scoped durable knowledge-base repositories."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from core.db.async_pg import AsyncDatabase, get_default_database
from core.db.pg import use_memory_repos
from core.rag.models import (
    AgentKnowledgeBinding,
    KnowledgeBaseRecord,
    KnowledgeBaseStatus,
    KnowledgeIngestionJob,
    KnowledgeJobState,
    KnowledgeSourceRecord,
    KnowledgeSourceStatus,
)


class KnowledgeNotFoundError(LookupError):
    pass


class KnowledgeConflictError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InMemoryKnowledgeRepository:
    """Local/test repository with the same tenant and state contracts as PostgreSQL."""

    def __init__(self) -> None:
        self._bases: dict[tuple[UUID, UUID], KnowledgeBaseRecord] = {}
        self._sources: dict[tuple[UUID, UUID, UUID], KnowledgeSourceRecord] = {}
        self._jobs: dict[tuple[UUID, UUID], KnowledgeIngestionJob] = {}
        self._bindings: list[AgentKnowledgeBinding] = []

    def create_knowledge_base(self, tenant_id: UUID, name: str) -> KnowledgeBaseRecord:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Knowledge base name is required.")
        if any(
            key[0] == tenant_id and record.name.casefold() == normalized.casefold()
            for key, record in self._bases.items()
        ):
            raise KnowledgeConflictError(
                "knowledge_name_exists",
                "A knowledge base with this name already exists.",
            )
        record = KnowledgeBaseRecord(tenant_id=tenant_id, name=normalized)
        self._bases[(tenant_id, record.knowledge_base_id)] = record
        return record

    def list_knowledge_bases(self, tenant_id: UUID) -> list[KnowledgeBaseRecord]:
        return sorted(
            (
                record
                for (owner, _), record in self._bases.items()
                if owner == tenant_id
            ),
            key=lambda item: (item.created_at, str(item.knowledge_base_id)),
        )

    def get_knowledge_base(
        self, tenant_id: UUID, knowledge_base_id: UUID
    ) -> KnowledgeBaseRecord:
        try:
            record = self._bases[(tenant_id, knowledge_base_id)]
        except KeyError as exc:
            raise KnowledgeNotFoundError("Knowledge base not found.") from exc
        return self._refresh_counts(record)

    def create_source(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        *,
        source_type: str,
        display_name: str,
        media_type: str,
        byte_count: int,
        checksum_sha256: str,
        object_reference: str,
    ) -> KnowledgeSourceRecord:
        base = self.get_knowledge_base(tenant_id, knowledge_base_id)
        revision = base.active_revision + 1
        duplicate = next(
            (
                item
                for (owner, base_id, _), item in self._sources.items()
                if owner == tenant_id
                and base_id == knowledge_base_id
                and item.revision == revision
                and item.checksum_sha256 == checksum_sha256
            ),
            None,
        )
        if duplicate is not None:
            return duplicate
        source = KnowledgeSourceRecord(
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_type=source_type,
            display_name=display_name,
            media_type=media_type,
            byte_count=byte_count,
            checksum_sha256=checksum_sha256,
            object_reference=object_reference,
            revision=revision,
        )
        self._sources[(tenant_id, knowledge_base_id, source.source_id)] = source
        job = KnowledgeIngestionJob(
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_id=source.source_id,
            idempotency_key=f"source:{source.source_id}:revision:{revision}",
        )
        self._jobs[(tenant_id, source.source_id)] = job
        base.status = self._build_status(base, KnowledgeBaseStatus.PROCESSING)
        base.updated_at = datetime.now(UTC)
        self._refresh_counts(base)
        return source

    def get_source(
        self, tenant_id: UUID, knowledge_base_id: UUID, source_id: UUID
    ) -> KnowledgeSourceRecord:
        self.get_knowledge_base(tenant_id, knowledge_base_id)
        try:
            return self._sources[(tenant_id, knowledge_base_id, source_id)]
        except KeyError as exc:
            raise KnowledgeNotFoundError("Knowledge source not found.") from exc

    def claim_next_job(
        self, worker_id: str, *, lease_seconds: int = 60
    ) -> tuple[KnowledgeIngestionJob, KnowledgeSourceRecord] | None:
        now = datetime.now(UTC)
        candidates = sorted(self._jobs.values(), key=lambda item: item.created_at)
        for job in candidates:
            if job.state == KnowledgeJobState.SUCCEEDED:
                continue
            if job.state == KnowledgeJobState.RUNNING and (
                job.lease_expires_at is None or job.lease_expires_at > now
            ):
                continue
            if job.state not in {KnowledgeJobState.QUEUED, KnowledgeJobState.RUNNING}:
                continue
            job.state = KnowledgeJobState.RUNNING
            job.lease_owner = worker_id
            job.lease_expires_at = now + timedelta(seconds=max(1, lease_seconds))
            job.updated_at = now
            source = next(
                item
                for (owner, _base, source_id), item in self._sources.items()
                if owner == job.tenant_id and source_id == job.source_id
            )
            source.status = KnowledgeSourceStatus.PARSING
            source.updated_at = now
            return job, source
        return None

    def store_chunks(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        source_id: UUID,
        chunks: list[Any],
    ) -> None:
        source = self.get_source(tenant_id, knowledge_base_id, source_id)
        source.status = KnowledgeSourceStatus.EMBEDDING
        source.chunk_count = len(chunks)
        source.updated_at = datetime.now(UTC)
        job = self._jobs[(tenant_id, source_id)]
        job.state = KnowledgeJobState.SUCCEEDED
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = source.updated_at

    def fail_job(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        source_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        self.mark_source_failed(
            tenant_id,
            knowledge_base_id,
            source_id,
            error_code=error_code,
            error_message=error_message[:500],
        )

    def delete_source(
        self, tenant_id: UUID, knowledge_base_id: UUID, source_id: UUID
    ) -> str:
        source = self.get_source(tenant_id, knowledge_base_id, source_id)
        del self._sources[(tenant_id, knowledge_base_id, source_id)]
        self._jobs.pop((tenant_id, source_id), None)
        base = self._bases[(tenant_id, knowledge_base_id)]
        base.updated_at = datetime.now(UTC)
        self._refresh_counts(base)
        return source.object_reference

    def mark_source_ready(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        source_id: UUID,
        *,
        chunk_count: int,
    ) -> KnowledgeSourceRecord:
        source = self.get_source(tenant_id, knowledge_base_id, source_id)
        source.status = KnowledgeSourceStatus.READY
        source.chunk_count = max(0, chunk_count)
        source.error_code = None
        source.error_message = None
        source.updated_at = datetime.now(UTC)
        job = self._jobs[(tenant_id, source_id)]
        job.state = KnowledgeJobState.SUCCEEDED
        job.updated_at = source.updated_at
        base = self._bases[(tenant_id, knowledge_base_id)]
        base.status = self._build_status(base, KnowledgeBaseStatus.READY)
        self._refresh_counts(base)
        return source

    def mark_source_failed(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        source_id: UUID,
        *,
        error_code: str,
        error_message: str | None = None,
    ) -> KnowledgeSourceRecord:
        source = self.get_source(tenant_id, knowledge_base_id, source_id)
        source.status = KnowledgeSourceStatus.FAILED
        source.error_code = error_code
        source.error_message = error_message
        source.updated_at = datetime.now(UTC)
        job = self._jobs[(tenant_id, source_id)]
        job.state = KnowledgeJobState.FAILED
        job.updated_at = source.updated_at
        base = self._bases[(tenant_id, knowledge_base_id)]
        base.status = self._build_status(base, KnowledgeBaseStatus.FAILED)
        self._refresh_counts(base)
        return source

    def retry_source(
        self, tenant_id: UUID, knowledge_base_id: UUID, source_id: UUID
    ) -> KnowledgeIngestionJob:
        source = self.get_source(tenant_id, knowledge_base_id, source_id)
        job = self._jobs[(tenant_id, source_id)]
        if source.status == KnowledgeSourceStatus.QUEUED:
            return job
        if source.status != KnowledgeSourceStatus.FAILED:
            raise KnowledgeConflictError(
                "source_not_retryable", "Only a failed source can be retried."
            )
        now = datetime.now(UTC)
        source.status = KnowledgeSourceStatus.QUEUED
        source.error_code = None
        source.error_message = None
        source.updated_at = now
        job.state = KnowledgeJobState.QUEUED
        job.attempt += 1
        job.updated_at = now
        base = self._bases[(tenant_id, knowledge_base_id)]
        base.status = self._build_status(base, KnowledgeBaseStatus.PROCESSING)
        base.updated_at = now
        return job

    def activate_knowledge_base(
        self, tenant_id: UUID, knowledge_base_id: UUID
    ) -> KnowledgeBaseRecord:
        base = self.get_knowledge_base(tenant_id, knowledge_base_id)
        target_revision = base.active_revision + 1
        sources = self._revision_sources(tenant_id, knowledge_base_id, target_revision)
        if not sources or any(
            source.status != KnowledgeSourceStatus.READY for source in sources
        ):
            raise KnowledgeConflictError(
                "knowledge_not_ready",
                "Every source in the next revision must be ready before activation.",
            )
        base.active_revision = target_revision
        base.status = KnowledgeBaseStatus.ACTIVE
        base.updated_at = datetime.now(UTC)
        return self._refresh_counts(base)

    def find_binding(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        knowledge_base_id: UUID,
        knowledge_revision: int,
    ) -> AgentKnowledgeBinding | None:
        return next(
            (
                binding
                for binding in self._bindings
                if binding.tenant_id == tenant_id
                and binding.agent_id == agent_id
                and binding.knowledge_base_id == knowledge_base_id
                and binding.knowledge_revision == knowledge_revision
            ),
            None,
        )

    def record_binding(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        agent_config_version: int,
        knowledge_base_id: UUID,
        knowledge_revision: int,
    ) -> AgentKnowledgeBinding:
        base = self.get_knowledge_base(tenant_id, knowledge_base_id)
        if (
            base.status != KnowledgeBaseStatus.ACTIVE
            or base.active_revision != knowledge_revision
        ):
            raise KnowledgeConflictError(
                "knowledge_not_active", "Knowledge base revision is not active."
            )
        existing = self.find_binding(
            tenant_id, agent_id, knowledge_base_id, knowledge_revision
        )
        if existing is not None:
            return existing
        binding = AgentKnowledgeBinding(
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_config_version=agent_config_version,
            knowledge_base_id=knowledge_base_id,
            knowledge_revision=knowledge_revision,
        )
        self._bindings.append(binding)
        return binding

    def aggregate_status(self, tenant_id: UUID) -> dict[str, Any]:
        bases = [
            self._refresh_counts(item) for item in self.list_knowledge_bases(tenant_id)
        ]
        return {
            "tenant_id": str(tenant_id),
            "status": "ready"
            if any(item.status == KnowledgeBaseStatus.ACTIVE for item in bases)
            else "empty"
            if not bases
            else "pending",
            "knowledge_base_count": len(bases),
            "ready_knowledge_base_count": sum(
                item.status == KnowledgeBaseStatus.ACTIVE for item in bases
            ),
            "source_count": sum(item.source_count for item in bases),
            "ready_source_count": sum(item.ready_source_count for item in bases),
            "total_chunks": sum(item.total_chunks for item in bases),
        }

    def _revision_sources(
        self, tenant_id: UUID, knowledge_base_id: UUID, revision: int
    ) -> list[KnowledgeSourceRecord]:
        return [
            source
            for (owner, base_id, _), source in self._sources.items()
            if owner == tenant_id
            and base_id == knowledge_base_id
            and source.revision == revision
        ]

    def _refresh_counts(self, base: KnowledgeBaseRecord) -> KnowledgeBaseRecord:
        revision = base.active_revision or 1
        sources = self._revision_sources(
            base.tenant_id, base.knowledge_base_id, revision
        )
        base.source_count = len(sources)
        base.ready_source_count = sum(
            source.status == KnowledgeSourceStatus.READY for source in sources
        )
        base.total_chunks = sum(
            source.chunk_count
            for source in sources
            if source.status == KnowledgeSourceStatus.READY
        )
        return base

    @staticmethod
    def _build_status(
        base: KnowledgeBaseRecord, pending_status: KnowledgeBaseStatus
    ) -> KnowledgeBaseStatus:
        if base.active_revision > 0:
            return KnowledgeBaseStatus.ACTIVE
        return pending_status


class PostgresKnowledgeRepository:
    """Psycopg repository; every operation uses the Phase 09 RLS transaction."""

    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def create_knowledge_base(
        self, tenant_id: UUID, name: str
    ) -> KnowledgeBaseRecord:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Knowledge base name is required.")
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            try:
                cursor = await connection.execute(
                    "INSERT INTO knowledge_bases (tenant_id, name) "
                    "VALUES (%s::uuid, %s) RETURNING id, status, active_revision, "
                    "created_at, updated_at",
                    (str(tenant_id), normalized),
                )
            except Exception as exc:
                if getattr(exc, "sqlstate", None) == "23505":
                    raise KnowledgeConflictError(
                        "knowledge_name_exists",
                        "A knowledge base with this name already exists.",
                    ) from exc
                raise
            row = await cursor.fetchone()
        return KnowledgeBaseRecord(
            tenant_id=tenant_id,
            name=normalized,
            knowledge_base_id=row[0],
            status=KnowledgeBaseStatus(row[1]),
            active_revision=row[2],
            created_at=row[3],
            updated_at=row[4],
        )

    async def list_knowledge_bases(self, tenant_id: UUID) -> list[KnowledgeBaseRecord]:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                self._summary_sql(order_by=True),
                (str(tenant_id),),
            )
            rows = await cursor.fetchall()
        return [self._base_from_row(tenant_id, row) for row in rows]

    async def get_knowledge_base(
        self, tenant_id: UUID, knowledge_base_id: UUID
    ) -> KnowledgeBaseRecord:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                self._summary_sql(by_id=True),
                (str(tenant_id), str(knowledge_base_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            raise KnowledgeNotFoundError("Knowledge base not found.")
        return self._base_from_row(tenant_id, row)

    async def get_source(
        self, tenant_id: UUID, knowledge_base_id: UUID, source_id: UUID
    ) -> KnowledgeSourceRecord:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT source_type, display_name, media_type, byte_count, "
                "checksum_sha256, object_reference, revision, status, chunk_count, "
                "error_code, error_message, created_at, updated_at "
                "FROM knowledge_sources WHERE tenant_id = %s::uuid "
                "AND knowledge_base_id = %s::uuid AND id = %s::uuid",
                (str(tenant_id), str(knowledge_base_id), str(source_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            raise KnowledgeNotFoundError("Knowledge source not found.")
        return KnowledgeSourceRecord(
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_id=source_id,
            source_type=row[0],
            display_name=row[1],
            media_type=row[2],
            byte_count=row[3],
            checksum_sha256=row[4],
            object_reference=row[5],
            revision=row[6],
            status=KnowledgeSourceStatus(row[7]),
            chunk_count=row[8],
            error_code=row[9],
            error_message=row[10],
            created_at=row[11],
            updated_at=row[12],
        )

    async def create_source(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        *,
        source_type: str,
        display_name: str,
        media_type: str,
        byte_count: int,
        checksum_sha256: str,
        object_reference: str,
    ) -> KnowledgeSourceRecord:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            base_cursor = await connection.execute(
                "SELECT active_revision FROM knowledge_bases "
                "WHERE tenant_id = %s::uuid "
                "AND id = %s::uuid FOR UPDATE",
                (str(tenant_id), str(knowledge_base_id)),
            )
            base = await base_cursor.fetchone()
            if base is None:
                raise KnowledgeNotFoundError("Knowledge base not found.")
            revision = int(base[0]) + 1
            duplicate_cursor = await connection.execute(
                "SELECT id FROM knowledge_sources WHERE tenant_id = %s::uuid "
                "AND knowledge_base_id = %s::uuid AND checksum_sha256 = %s "
                "AND revision = %s",
                (str(tenant_id), str(knowledge_base_id), checksum_sha256, revision),
            )
            duplicate = await duplicate_cursor.fetchone()
            if duplicate is not None:
                duplicate_id = duplicate[0]
            else:
                cursor = await connection.execute(
                    "INSERT INTO knowledge_sources (tenant_id, knowledge_base_id, "
                    "source_type, display_name, media_type, byte_count, "
                    "checksum_sha256, "
                    "object_reference, revision, status) VALUES "
                    "(%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, 'queued') "
                    "RETURNING id",
                    (
                        str(tenant_id),
                        str(knowledge_base_id),
                        source_type,
                        display_name,
                        media_type,
                        byte_count,
                        checksum_sha256,
                        object_reference,
                        revision,
                    ),
                )
                duplicate_id = (await cursor.fetchone())[0]
                await connection.execute(
                    "INSERT INTO knowledge_ingestion_jobs "
                    "(tenant_id, knowledge_base_id, source_id, idempotency_key) "
                    "VALUES (%s::uuid, %s::uuid, %s::uuid, %s)",
                    (
                        str(tenant_id),
                        str(knowledge_base_id),
                        str(duplicate_id),
                        f"source:{duplicate_id}:revision:{revision}",
                    ),
                )
                await connection.execute(
                    "UPDATE knowledge_bases SET status = CASE WHEN active_revision > 0 "
                    "THEN 'active' ELSE 'processing' END, updated_at = NOW() "
                    "WHERE tenant_id = %s::uuid AND id = %s::uuid",
                    (str(tenant_id), str(knowledge_base_id)),
                )
        return await self.get_source(tenant_id, knowledge_base_id, duplicate_id)

    async def claim_next_job(
        self, worker_id: str, *, lease_seconds: int = 60
    ) -> tuple[KnowledgeIngestionJob, KnowledgeSourceRecord] | None:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT j.id, j.tenant_id, j.knowledge_base_id, j.source_id, "
                "j.idempotency_key, j.attempt, j.created_at, j.updated_at "
                "FROM knowledge_ingestion_jobs j WHERE "
                "(j.state = 'queued' OR "
                "(j.state = 'running' AND j.lease_expires_at < NOW())) "
                "AND (j.retry_at IS NULL OR j.retry_at <= NOW()) "
                "ORDER BY j.created_at FOR UPDATE SKIP LOCKED LIMIT 1"
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            job_id, tenant_id, base_id, source_id = row[:4]
            lease_cursor = await connection.execute(
                "UPDATE knowledge_ingestion_jobs SET state = 'running', "
                "lease_owner = %s, lease_expires_at = "
                "NOW() + (%s * INTERVAL '1 second'), updated_at = NOW() "
                "WHERE id = %s::uuid RETURNING lease_expires_at, updated_at",
                (worker_id, max(1, lease_seconds), str(job_id)),
            )
            lease_expires_at, updated_at = await lease_cursor.fetchone()
            await connection.execute(
                "UPDATE knowledge_sources SET status = 'parsing', updated_at = NOW() "
                "WHERE tenant_id = %s::uuid AND id = %s::uuid",
                (str(tenant_id), str(source_id)),
            )
        source = await self.get_source(tenant_id, base_id, source_id)
        return (
            KnowledgeIngestionJob(
                tenant_id=tenant_id,
                knowledge_base_id=base_id,
                source_id=source_id,
                job_id=job_id,
                idempotency_key=row[4],
                state=KnowledgeJobState.RUNNING,
                attempt=row[5],
                lease_owner=worker_id,
                lease_expires_at=lease_expires_at,
                created_at=row[6],
                updated_at=updated_at,
            ),
            source,
        )

    async def store_chunks(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        source_id: UUID,
        chunks: list[Any],
    ) -> None:
        source = await self.get_source(tenant_id, knowledge_base_id, source_id)
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            await connection.execute(
                "DELETE FROM knowledge_chunks WHERE tenant_id = %s::uuid "
                "AND knowledge_source_id = %s::uuid",
                (str(tenant_id), str(source_id)),
            )
            for ordinal, chunk in enumerate(chunks):
                await connection.execute(
                    "INSERT INTO knowledge_chunks (id, tenant_id, source_document_id, "
                    "text, metadata_jsonb, knowledge_base_id, knowledge_source_id, "
                    "revision, ordinal, token_count, citation_jsonb, content_hash) "
                    "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb, %s::uuid, "
                    "%s::uuid, %s, %s, %s, %s::jsonb, %s)",
                    (
                        str(chunk.chunk_id),
                        str(tenant_id),
                        str(source_id),
                        chunk.text,
                        json.dumps(chunk.metadata),
                        str(knowledge_base_id),
                        str(source_id),
                        source.revision,
                        ordinal,
                        len(chunk.text.split()),
                        json.dumps(chunk.metadata.get("citation", {})),
                        hashlib.sha256(chunk.text.encode()).hexdigest(),
                    ),
                )
            await connection.execute(
                "UPDATE knowledge_sources SET status = 'embedding', chunk_count = %s, "
                "parser_version = 'phase10b-v1', error_code = NULL, "
                "error_message = NULL, "
                "updated_at = NOW() WHERE tenant_id = %s::uuid AND id = %s::uuid",
                (len(chunks), str(tenant_id), str(source_id)),
            )
            await connection.execute(
                "UPDATE knowledge_ingestion_jobs SET state = 'succeeded', "
                "lease_owner = NULL, lease_expires_at = NULL, "
                "progress_jsonb = %s::jsonb, updated_at = NOW() "
                "WHERE tenant_id = %s::uuid AND source_id = %s::uuid",
                (
                    json.dumps({"chunks": len(chunks)}),
                    str(tenant_id),
                    str(source_id),
                ),
            )

    async def fail_job(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        source_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        safe_message = error_message[:500]
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            await connection.execute(
                "UPDATE knowledge_sources SET status = 'failed', error_code = %s, "
                "error_message = %s, updated_at = NOW() WHERE tenant_id = %s::uuid "
                "AND knowledge_base_id = %s::uuid AND id = %s::uuid",
                (
                    error_code,
                    safe_message,
                    str(tenant_id),
                    str(knowledge_base_id),
                    str(source_id),
                ),
            )
            await connection.execute(
                "UPDATE knowledge_ingestion_jobs SET state = 'failed', "
                "lease_owner = NULL, lease_expires_at = NULL, "
                "last_error_code = %s, last_error_message = %s, updated_at = NOW() "
                "WHERE tenant_id = %s::uuid AND source_id = %s::uuid",
                (error_code, safe_message, str(tenant_id), str(source_id)),
            )

    async def delete_source(
        self, tenant_id: UUID, knowledge_base_id: UUID, source_id: UUID
    ) -> str:
        source = await self.get_source(tenant_id, knowledge_base_id, source_id)
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            await connection.execute(
                "DELETE FROM knowledge_sources WHERE tenant_id = %s::uuid "
                "AND knowledge_base_id = %s::uuid AND id = %s::uuid",
                (str(tenant_id), str(knowledge_base_id), str(source_id)),
            )
        return source.object_reference

    async def retry_source(
        self, tenant_id: UUID, knowledge_base_id: UUID, source_id: UUID
    ) -> KnowledgeIngestionJob:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            source_cursor = await connection.execute(
                "SELECT status FROM knowledge_sources WHERE tenant_id = %s::uuid "
                "AND knowledge_base_id = %s::uuid AND id = %s::uuid FOR UPDATE",
                (str(tenant_id), str(knowledge_base_id), str(source_id)),
            )
            source_row = await source_cursor.fetchone()
            if source_row is None:
                raise KnowledgeNotFoundError("Knowledge source not found.")
            if source_row[0] not in ("failed", "queued"):
                raise KnowledgeConflictError(
                    "source_not_retryable", "Only a failed source can be retried."
                )
            if source_row[0] == "failed":
                await connection.execute(
                    "UPDATE knowledge_sources SET status = 'queued', "
                    "error_code = NULL, error_message = NULL, updated_at = NOW() "
                    "WHERE tenant_id = %s::uuid "
                    "AND knowledge_base_id = %s::uuid AND id = %s::uuid",
                    (str(tenant_id), str(knowledge_base_id), str(source_id)),
                )
                await connection.execute(
                    "UPDATE knowledge_ingestion_jobs SET state = 'queued', "
                    "attempt = attempt + 1, lease_owner = NULL, "
                    "lease_expires_at = NULL, updated_at = NOW() "
                    "WHERE tenant_id = %s::uuid AND source_id = %s::uuid",
                    (str(tenant_id), str(source_id)),
                )
            cursor = await connection.execute(
                "SELECT id, idempotency_key, state, attempt, created_at, updated_at "
                "FROM knowledge_ingestion_jobs WHERE tenant_id = %s::uuid "
                "AND source_id = %s::uuid",
                (str(tenant_id), str(source_id)),
            )
            row = await cursor.fetchone()
        return KnowledgeIngestionJob(
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_id=source_id,
            job_id=row[0],
            idempotency_key=row[1],
            state=KnowledgeJobState(row[2]),
            attempt=row[3],
            created_at=row[4],
            updated_at=row[5],
        )

    async def activate_knowledge_base(
        self, tenant_id: UUID, knowledge_base_id: UUID
    ) -> KnowledgeBaseRecord:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT active_revision FROM knowledge_bases "
                "WHERE tenant_id = %s::uuid "
                "AND id = %s::uuid FOR UPDATE",
                (str(tenant_id), str(knowledge_base_id)),
            )
            row = await cursor.fetchone()
            if row is None:
                raise KnowledgeNotFoundError("Knowledge base not found.")
            revision = int(row[0]) + 1
            counts_cursor = await connection.execute(
                "SELECT COUNT(*), COUNT(*) FILTER (WHERE status = 'ready') "
                "FROM knowledge_sources WHERE tenant_id = %s::uuid "
                "AND knowledge_base_id = %s::uuid AND revision = %s",
                (str(tenant_id), str(knowledge_base_id), revision),
            )
            total, ready = await counts_cursor.fetchone()
            if total == 0 or total != ready:
                raise KnowledgeConflictError(
                    "knowledge_not_ready",
                    "Every source in the next revision must be ready "
                    "before activation.",
                )
            await connection.execute(
                "UPDATE knowledge_bases SET status = 'active', active_revision = %s, "
                "updated_at = NOW() WHERE tenant_id = %s::uuid AND id = %s::uuid",
                (revision, str(tenant_id), str(knowledge_base_id)),
            )
        return await self.get_knowledge_base(tenant_id, knowledge_base_id)

    async def find_binding(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        knowledge_base_id: UUID,
        knowledge_revision: int,
    ) -> AgentKnowledgeBinding | None:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT id, agent_config_version, created_at "
                "FROM agent_knowledge_bindings "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid "
                "AND knowledge_base_id = %s::uuid AND knowledge_revision = %s "
                "ORDER BY created_at DESC LIMIT 1",
                (
                    str(tenant_id),
                    str(agent_id),
                    str(knowledge_base_id),
                    knowledge_revision,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return AgentKnowledgeBinding(
            binding_id=row[0],
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_config_version=row[1],
            knowledge_base_id=knowledge_base_id,
            knowledge_revision=knowledge_revision,
            created_at=row[2],
        )

    async def record_binding(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        agent_config_version: int,
        knowledge_base_id: UUID,
        knowledge_revision: int,
    ) -> AgentKnowledgeBinding:
        existing = await self.find_binding(
            tenant_id, agent_id, knowledge_base_id, knowledge_revision
        )
        if existing is not None:
            return existing
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "INSERT INTO agent_knowledge_bindings (tenant_id, agent_id, "
                "agent_version_id, agent_config_version, knowledge_base_id, "
                "knowledge_revision) SELECT %s::uuid, %s::uuid, version_id, %s, "
                "%s::uuid, %s FROM agent_config_versions WHERE tenant_id = %s::uuid "
                "AND agent_id = %s::uuid AND version = %s "
                "ON CONFLICT (tenant_id, agent_id, knowledge_base_id, "
                "knowledge_revision) DO UPDATE SET "
                "agent_version_id = EXCLUDED.agent_version_id, "
                "agent_config_version = EXCLUDED.agent_config_version "
                "RETURNING id, created_at",
                (
                    str(tenant_id),
                    str(agent_id),
                    agent_config_version,
                    str(knowledge_base_id),
                    knowledge_revision,
                    str(tenant_id),
                    str(agent_id),
                    agent_config_version,
                ),
            )
            row = await cursor.fetchone()
            if row is None:
                raise KnowledgeConflictError(
                    "agent_version_missing", "Published agent version was not found."
                )
        return AgentKnowledgeBinding(
            binding_id=row[0],
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_config_version=agent_config_version,
            knowledge_base_id=knowledge_base_id,
            knowledge_revision=knowledge_revision,
            created_at=row[1],
        )

    async def aggregate_status(self, tenant_id: UUID) -> dict[str, Any]:
        bases = await self.list_knowledge_bases(tenant_id)
        return {
            "tenant_id": str(tenant_id),
            "status": "ready"
            if any(item.status == KnowledgeBaseStatus.ACTIVE for item in bases)
            else "empty"
            if not bases
            else "pending",
            "knowledge_base_count": len(bases),
            "ready_knowledge_base_count": sum(
                item.status == KnowledgeBaseStatus.ACTIVE for item in bases
            ),
            "source_count": sum(item.source_count for item in bases),
            "ready_source_count": sum(item.ready_source_count for item in bases),
            "total_chunks": sum(item.total_chunks for item in bases),
        }

    @staticmethod
    def _summary_sql(*, by_id: bool = False, order_by: bool = False) -> str:
        query = (
            "SELECT kb.id, kb.name, kb.status, kb.active_revision, kb.created_at, "
            "kb.updated_at, COUNT(ks.id), "
            "COUNT(ks.id) FILTER (WHERE ks.status = 'ready'), "
            "COALESCE(SUM(ks.chunk_count) FILTER (WHERE ks.status = 'ready'), 0) "
            "FROM knowledge_bases kb LEFT JOIN knowledge_sources ks ON "
            "ks.tenant_id = kb.tenant_id AND ks.knowledge_base_id = kb.id AND "
            "ks.revision = CASE WHEN kb.active_revision = 0 "
            "THEN 1 ELSE kb.active_revision END "
            "WHERE kb.tenant_id = %s::uuid "
        )
        if by_id:
            query += "AND kb.id = %s::uuid "
        query += "GROUP BY kb.id"
        if order_by:
            query += " ORDER BY kb.created_at, kb.id"
        return query

    @staticmethod
    def _base_from_row(tenant_id: UUID, row: tuple[Any, ...]) -> KnowledgeBaseRecord:
        return KnowledgeBaseRecord(
            tenant_id=tenant_id,
            knowledge_base_id=row[0],
            name=row[1],
            status=KnowledgeBaseStatus(row[2]),
            active_revision=row[3],
            created_at=row[4],
            updated_at=row[5],
            source_count=row[6],
            ready_source_count=row[7],
            total_chunks=row[8],
        )


_default_knowledge_repository: Any | None = None


def get_default_knowledge_repository() -> Any:
    global _default_knowledge_repository
    if _default_knowledge_repository is None:
        _default_knowledge_repository = (
            InMemoryKnowledgeRepository()
            if use_memory_repos()
            else PostgresKnowledgeRepository()
        )
    return _default_knowledge_repository


def reset_default_knowledge_repository() -> Any:
    global _default_knowledge_repository
    _default_knowledge_repository = None
    return get_default_knowledge_repository()


def record_to_dict(record: Any) -> dict[str, Any]:
    value = asdict(record)
    return {
        key: item.value if hasattr(item, "value") else item
        for key, item in value.items()
    }
