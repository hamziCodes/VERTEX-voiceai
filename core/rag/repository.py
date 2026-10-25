"""Durable embedding work and agent-scoped pgvector retrieval repositories."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from core.db.async_pg import AsyncDatabase, get_default_database
from core.rag.embedders.base import EXPECTED_EMBEDDING_DIMENSIONS, EmbeddingBatch
from core.rag.models import KnowledgeBaseChunk


class KnowledgeVectorError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.safe_message = message


@dataclass(frozen=True, slots=True)
class EmbeddingWork:
    job_id: UUID
    tenant_id: UUID
    knowledge_base_id: UUID
    source_id: UUID
    revision: int
    chunks: list[KnowledgeBaseChunk]


def _validate_batch(chunks: list[KnowledgeBaseChunk], batch: EmbeddingBatch) -> None:
    if batch.dimensions != EXPECTED_EMBEDDING_DIMENSIONS or any(
        len(vector) != EXPECTED_EMBEDDING_DIMENSIONS for vector in batch.vectors
    ):
        raise KnowledgeVectorError(
            "embedding_dimension_mismatch",
            f"Embeddings must have {EXPECTED_EMBEDDING_DIMENSIONS} dimensions.",
        )
    if len(batch.vectors) != len(chunks):
        raise KnowledgeVectorError(
            "embedding_count_mismatch", "Embedding count does not match chunk count."
        )
    if any(
        not all(math.isfinite(value) for value in vector) for vector in batch.vectors
    ):
        raise KnowledgeVectorError(
            "embedding_value_invalid", "Embedding contains a non-finite value."
        )


class InMemoryKnowledgeVectorRepository:
    def __init__(self) -> None:
        self.chunks: list[KnowledgeBaseChunk] = []
        self._jobs: dict[UUID, dict[str, Any]] = {}
        self._sources: dict[UUID, dict[str, Any]] = {}
        self._bindings: set[tuple[UUID, UUID, int | None, UUID, int]] = set()

    def add_chunk(self, chunk: KnowledgeBaseChunk) -> None:
        self.chunks.append(chunk)

    def bind(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        knowledge_base_id: UUID,
        *,
        revision: int,
        agent_config_version: int | None = None,
    ) -> None:
        self._bindings.add(
            (tenant_id, agent_id, agent_config_version, knowledge_base_id, revision)
        )

    def queue_source(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        source_id: UUID,
        *,
        revision: int,
        chunks: list[KnowledgeBaseChunk],
    ) -> None:
        for ordinal, chunk in enumerate(chunks):
            chunk.tenant_id = tenant_id
            chunk.knowledge_base_id = knowledge_base_id
            chunk.source_document_id = source_id
            chunk.revision = revision
            chunk.ordinal = ordinal
            self.chunks.append(chunk)
        job_id = uuid4()
        self._sources[source_id] = {
            "tenant_id": tenant_id,
            "knowledge_base_id": knowledge_base_id,
            "revision": revision,
            "status": "embedding",
            "failure_code": None,
        }
        self._jobs[source_id] = {
            "job_id": job_id,
            "state": "queued",
            "lease_owner": None,
            "lease_expires_at": None,
            "attempt": 1,
        }

    def claim_embedding_job(
        self, worker_id: str, *, lease_seconds: int = 60
    ) -> EmbeddingWork | None:
        now = datetime.now(UTC)
        for source_id, job in self._jobs.items():
            if job["state"] == "succeeded" or job["state"] == "failed":
                continue
            if job["state"] == "running" and job["lease_expires_at"] > now:
                continue
            source = self._sources[source_id]
            job["state"] = "running"
            job["lease_owner"] = worker_id
            job["lease_expires_at"] = now + timedelta(seconds=max(1, lease_seconds))
            chunks = [
                chunk for chunk in self.chunks if chunk.source_document_id == source_id
            ]
            return EmbeddingWork(
                job_id=job["job_id"],
                tenant_id=source["tenant_id"],
                knowledge_base_id=source["knowledge_base_id"],
                source_id=source_id,
                revision=source["revision"],
                chunks=chunks,
            )
        return None

    def complete_embeddings(self, work: EmbeddingWork, batch: EmbeddingBatch) -> None:
        _validate_batch(work.chunks, batch)
        for chunk, vector in zip(work.chunks, batch.vectors, strict=True):
            chunk.embedding = vector
            chunk.embedding_model = batch.model_id
            chunk.embedding_version = batch.version
        self._jobs[work.source_id]["state"] = "succeeded"
        self._sources[work.source_id]["status"] = "ready"
        self._sources[work.source_id]["failure_code"] = None

    def fail_embedding(self, work: EmbeddingWork, *, code: str, message: str) -> None:
        del message
        self._jobs[work.source_id]["state"] = "failed"
        self._sources[work.source_id]["status"] = "failed"
        self._sources[work.source_id]["failure_code"] = code

    def retry(self, source_id: UUID) -> None:
        self._jobs[source_id]["state"] = "queued"
        self._jobs[source_id]["attempt"] += 1
        self._sources[source_id]["status"] = "embedding"
        self._sources[source_id]["failure_code"] = None

    def source_status(self, source_id: UUID) -> str:
        return str(self._sources[source_id]["status"])

    def failure_code(self, source_id: UUID) -> str | None:
        value = self._sources[source_id]["failure_code"]
        return None if value is None else str(value)

    async def search(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID,
        agent_config_version: int | None = None,
        knowledge_base_id: UUID,
        revision: int | None = None,
        query_vector: list[float],
        embedding_model: str,
        embedding_version: str,
        top_k: int,
    ) -> list[KnowledgeBaseChunk]:
        matching_revisions = {
            bound_revision
            for (
                bound_tenant,
                bound_agent,
                bound_version,
                bound_base,
                bound_revision,
            ) in self._bindings
            if bound_tenant == tenant_id
            and bound_agent == agent_id
            and bound_base == knowledge_base_id
            and (agent_config_version is None or bound_version == agent_config_version)
            and (revision is None or bound_revision == revision)
        }
        if len(matching_revisions) != 1:
            raise KnowledgeVectorError(
                "knowledge_binding_required",
                "Agent is not bound to this knowledge revision.",
            )
        active_revision = next(iter(matching_revisions))
        if len(query_vector) != EXPECTED_EMBEDDING_DIMENSIONS:
            raise KnowledgeVectorError(
                "embedding_dimension_mismatch", "Query embedding dimension is invalid."
            )
        scored: list[tuple[float, KnowledgeBaseChunk]] = []
        for chunk in self.chunks:
            if (
                chunk.tenant_id != tenant_id
                or chunk.knowledge_base_id != knowledge_base_id
                or chunk.revision != active_revision
                or len(chunk.embedding) != EXPECTED_EMBEDDING_DIMENSIONS
                or chunk.embedding_model != embedding_model
                or chunk.embedding_version != embedding_version
            ):
                continue
            score = sum(
                a * b for a, b in zip(query_vector, chunk.embedding, strict=True)
            )
            result = KnowledgeBaseChunk(
                tenant_id=chunk.tenant_id,
                chunk_id=chunk.chunk_id,
                source_document_id=chunk.source_document_id,
                text=chunk.text,
                embedding=[],
                metadata=chunk.metadata,
                knowledge_base_id=chunk.knowledge_base_id,
                revision=chunk.revision,
                ordinal=chunk.ordinal,
                citation=chunk.metadata.get("citation", chunk.citation),
                score=float(score),
                embedding_model=chunk.embedding_model,
                embedding_version=chunk.embedding_version,
            )
            scored.append((float(score), result))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[: max(1, min(top_k, 10))]]

    async def preview_search(
        self,
        *,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        revision: int,
        query_vector: list[float],
        embedding_model: str,
        embedding_version: str,
        top_k: int,
    ) -> list[KnowledgeBaseChunk]:
        if len(query_vector) != EXPECTED_EMBEDDING_DIMENSIONS:
            raise KnowledgeVectorError(
                "embedding_dimension_mismatch", "Query embedding dimension is invalid."
            )
        scored: list[tuple[float, KnowledgeBaseChunk]] = []
        for chunk in self.chunks:
            if (
                chunk.tenant_id != tenant_id
                or chunk.knowledge_base_id != knowledge_base_id
                or chunk.revision != revision
                or chunk.embedding_model != embedding_model
                or chunk.embedding_version != embedding_version
                or len(chunk.embedding) != EXPECTED_EMBEDDING_DIMENSIONS
            ):
                continue
            score = sum(
                a * b for a, b in zip(query_vector, chunk.embedding, strict=True)
            )
            result = KnowledgeBaseChunk(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                chunk_id=chunk.chunk_id,
                source_document_id=chunk.source_document_id,
                revision=revision,
                ordinal=chunk.ordinal,
                text=chunk.text,
                metadata=chunk.metadata,
                citation=chunk.citation or chunk.metadata.get("citation", {}),
                score=float(score),
                embedding_model=chunk.embedding_model,
                embedding_version=chunk.embedding_version,
            )
            scored.append((float(score), result))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[: max(1, min(top_k, 8))]]


class PostgresKnowledgeVectorRepository:
    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def claim_embedding_job(
        self, worker_id: str, *, lease_seconds: int = 60
    ) -> EmbeddingWork | None:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT j.id, j.tenant_id, j.knowledge_base_id, j.source_id, "
                "s.revision FROM knowledge_ingestion_jobs j "
                "JOIN knowledge_sources s ON s.tenant_id = j.tenant_id "
                "AND s.id = j.source_id WHERE "
                "(j.state = 'queued' OR (j.state = 'running' "
                "AND j.lease_expires_at < NOW())) "
                "AND j.progress_jsonb->>'stage' = 'embedding' "
                "ORDER BY j.created_at FOR UPDATE OF j SKIP LOCKED LIMIT 1"
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            job_id, tenant_id, base_id, source_id, revision = row
            await connection.execute(
                "UPDATE knowledge_ingestion_jobs SET state = 'running', "
                "lease_owner = %s, lease_expires_at = "
                "NOW() + (%s * INTERVAL '1 second'), updated_at = NOW() "
                "WHERE id = %s::uuid",
                (worker_id, max(1, lease_seconds), str(job_id)),
            )
            chunks_cursor = await connection.execute(
                "SELECT id, text, metadata_jsonb, ordinal, citation_jsonb "
                "FROM knowledge_chunks WHERE tenant_id = %s::uuid "
                "AND knowledge_source_id = %s::uuid ORDER BY ordinal",
                (str(tenant_id), str(source_id)),
            )
            rows = await chunks_cursor.fetchall()
        chunks = [
            KnowledgeBaseChunk(
                chunk_id=item[0],
                tenant_id=tenant_id,
                source_document_id=source_id,
                text=item[1],
                metadata=item[2] or {},
                knowledge_base_id=base_id,
                revision=revision,
                ordinal=item[3],
                citation=item[4] or {},
            )
            for item in rows
        ]
        return EmbeddingWork(job_id, tenant_id, base_id, source_id, revision, chunks)

    async def complete_embeddings(
        self, work: EmbeddingWork, batch: EmbeddingBatch
    ) -> None:
        _validate_batch(work.chunks, batch)
        async with self.database.tenant_transaction(str(work.tenant_id)) as connection:
            for chunk, vector in zip(work.chunks, batch.vectors, strict=True):
                await connection.execute(
                    "UPDATE knowledge_chunks SET embedding = %s::vector, "
                    "embedding_model = %s, embedding_version = %s "
                    "WHERE tenant_id = %s::uuid AND id = %s::uuid",
                    (
                        _vector_literal(vector),
                        batch.model_id,
                        batch.version,
                        str(work.tenant_id),
                        str(chunk.chunk_id),
                    ),
                )
            await connection.execute(
                "UPDATE knowledge_sources SET status = 'ready', error_code = NULL, "
                "error_message = NULL, updated_at = NOW() WHERE tenant_id = %s::uuid "
                "AND id = %s::uuid",
                (str(work.tenant_id), str(work.source_id)),
            )
            await connection.execute(
                "UPDATE knowledge_ingestion_jobs SET state = 'succeeded', "
                "lease_owner = NULL, lease_expires_at = NULL, "
                "progress_jsonb = %s::jsonb, updated_at = NOW() "
                "WHERE tenant_id = %s::uuid AND id = %s::uuid",
                (
                    json.dumps(
                        {
                            "stage": "complete",
                            "chunks": len(work.chunks),
                            "model": batch.model_id,
                            "version": batch.version,
                        }
                    ),
                    str(work.tenant_id),
                    str(work.job_id),
                ),
            )
            await connection.execute(
                "UPDATE knowledge_bases kb SET status = CASE "
                "WHEN kb.active_revision > 0 THEN 'active' "
                "WHEN NOT EXISTS (SELECT 1 FROM knowledge_sources s "
                "WHERE s.tenant_id = kb.tenant_id AND s.knowledge_base_id = kb.id "
                "AND s.revision = %s AND s.status <> 'ready') THEN 'ready' "
                "ELSE 'processing' END, updated_at = NOW() "
                "WHERE kb.tenant_id = %s::uuid AND kb.id = %s::uuid",
                (work.revision, str(work.tenant_id), str(work.knowledge_base_id)),
            )

    async def fail_embedding(
        self, work: EmbeddingWork, *, code: str, message: str
    ) -> None:
        safe_message = message[:500]
        async with self.database.tenant_transaction(str(work.tenant_id)) as connection:
            await connection.execute(
                "UPDATE knowledge_sources SET status = 'failed', error_code = %s, "
                "error_message = %s, updated_at = NOW() WHERE tenant_id = %s::uuid "
                "AND id = %s::uuid",
                (code, safe_message, str(work.tenant_id), str(work.source_id)),
            )
            await connection.execute(
                "UPDATE knowledge_ingestion_jobs SET state = 'failed', "
                "lease_owner = NULL, lease_expires_at = NULL, last_error_code = %s, "
                "last_error_message = %s, updated_at = NOW() "
                "WHERE tenant_id = %s::uuid AND id = %s::uuid",
                (code, safe_message, str(work.tenant_id), str(work.job_id)),
            )
            await connection.execute(
                "UPDATE knowledge_bases SET status = CASE WHEN active_revision > 0 "
                "THEN 'active' ELSE 'failed' END, updated_at = NOW() "
                "WHERE tenant_id = %s::uuid AND id = %s::uuid",
                (str(work.tenant_id), str(work.knowledge_base_id)),
            )

    async def search(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID,
        agent_config_version: int | None = None,
        knowledge_base_id: UUID,
        revision: int | None = None,
        query_vector: list[float],
        embedding_model: str,
        embedding_version: str,
        top_k: int,
    ) -> list[KnowledgeBaseChunk]:
        if len(query_vector) != EXPECTED_EMBEDDING_DIMENSIONS:
            raise KnowledgeVectorError(
                "embedding_dimension_mismatch", "Query embedding dimension is invalid."
            )
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            if agent_config_version is not None:
                binding_cursor = await connection.execute(
                    "SELECT knowledge_revision FROM agent_knowledge_bindings "
                    "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid "
                    "AND agent_config_version = %s AND knowledge_base_id = %s::uuid "
                    "ORDER BY created_at DESC LIMIT 1",
                    (
                        str(tenant_id),
                        str(agent_id),
                        agent_config_version,
                        str(knowledge_base_id),
                    ),
                )
            elif revision is not None:
                binding_cursor = await connection.execute(
                    "SELECT knowledge_revision FROM agent_knowledge_bindings "
                    "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid "
                    "AND knowledge_base_id = %s::uuid AND knowledge_revision = %s "
                    "LIMIT 1",
                    (str(tenant_id), str(agent_id), str(knowledge_base_id), revision),
                )
            else:
                raise KnowledgeVectorError(
                    "knowledge_scope_required",
                    "Agent configuration version or knowledge revision is required.",
                )
            binding = await binding_cursor.fetchone()
            if binding is None:
                raise KnowledgeVectorError(
                    "knowledge_binding_required",
                    "Agent is not bound to this knowledge revision.",
                )
            active_revision = int(binding[0])
            cursor = await connection.execute(
                "SELECT id, knowledge_source_id, text, metadata_jsonb, ordinal, "
                "citation_jsonb, embedding_model, embedding_version, "
                "1 - (embedding <=> %s::vector) AS score "
                "FROM knowledge_chunks WHERE tenant_id = %s::uuid "
                "AND knowledge_base_id = %s::uuid AND revision = %s "
                "AND embedding_model = %s AND embedding_version = %s "
                "AND embedding IS NOT NULL ORDER BY embedding <=> %s::vector "
                "LIMIT %s",
                (
                    _vector_literal(query_vector),
                    str(tenant_id),
                    str(knowledge_base_id),
                    active_revision,
                    embedding_model,
                    embedding_version,
                    _vector_literal(query_vector),
                    max(1, min(top_k, 10)),
                ),
            )
            rows = await cursor.fetchall()
        return [
            KnowledgeBaseChunk(
                chunk_id=row[0],
                tenant_id=tenant_id,
                source_document_id=row[1],
                text=row[2],
                metadata=row[3] or {},
                knowledge_base_id=knowledge_base_id,
                revision=active_revision,
                ordinal=row[4],
                citation=row[5] or {},
                embedding_model=row[6],
                embedding_version=row[7],
                score=float(row[8]),
            )
            for row in rows
        ]

    async def preview_search(
        self,
        *,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        revision: int,
        query_vector: list[float],
        embedding_model: str,
        embedding_version: str,
        top_k: int,
    ) -> list[KnowledgeBaseChunk]:
        if len(query_vector) != EXPECTED_EMBEDDING_DIMENSIONS:
            raise KnowledgeVectorError(
                "embedding_dimension_mismatch", "Query embedding dimension is invalid."
            )
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT c.id, c.knowledge_source_id, c.text, c.metadata_jsonb, "
                "c.ordinal, c.citation_jsonb, c.embedding_model, "
                "c.embedding_version, 1 - (c.embedding <=> %s::vector) AS score "
                "FROM knowledge_chunks c JOIN knowledge_sources s "
                "ON s.tenant_id = c.tenant_id AND s.id = c.knowledge_source_id "
                "WHERE c.tenant_id = %s::uuid AND c.knowledge_base_id = %s::uuid "
                "AND c.revision = %s AND s.status = 'ready' "
                "AND c.embedding_model = %s AND c.embedding_version = %s "
                "AND c.embedding IS NOT NULL ORDER BY c.embedding <=> %s::vector "
                "LIMIT %s",
                (
                    _vector_literal(query_vector),
                    str(tenant_id),
                    str(knowledge_base_id),
                    revision,
                    embedding_model,
                    embedding_version,
                    _vector_literal(query_vector),
                    max(1, min(top_k, 8)),
                ),
            )
            rows = await cursor.fetchall()
        return [
            KnowledgeBaseChunk(
                chunk_id=row[0],
                tenant_id=tenant_id,
                source_document_id=row[1],
                text=row[2],
                metadata=row[3] or {},
                knowledge_base_id=knowledge_base_id,
                revision=revision,
                ordinal=row[4],
                citation=row[5] or {},
                embedding_model=row[6],
                embedding_version=row[7],
                score=float(row[8]),
            )
            for row in rows
        ]


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(format(value, ".9g") for value in vector) + "]"
