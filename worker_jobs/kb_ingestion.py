"""UCVE Knowledge Base Ingestion Worker Job — Processes documents into vector embeddings."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

from core.observability.logging import get_logger
from core.rag.embedder_policy import EmbedderPolicy
from core.rag.ingestion.worker import IngestionWorker
from core.rag.models import KnowledgeBaseChunk, KnowledgeBaseSource

logger = get_logger("ucve.jobs.kb_ingestion")


class KBIngestionJob:
    """Async background worker job for chunking and embedding knowledge base documents."""

    def __init__(self, db_pool: Any | None = None, compliance_tier: str = "standard") -> None:
        self.db_pool = db_pool
        self.compliance_tier = compliance_tier
        self.embedder_policy = EmbedderPolicy(compliance_tier=compliance_tier)
        self.ingestion_worker = IngestionWorker()

    async def process_document(
        self,
        tenant_id: UUID,
        source_id: UUID,
        document_text: str,
        content_type: str = "text/plain",
        agent_id: UUID | None = None,
    ) -> list[KnowledgeBaseChunk]:
        """Ingest document text, generate chunks and embeddings, and persist to pgvector table."""
        source = KnowledgeBaseSource(
            source_id=source_id,
            tenant_id=tenant_id,
            name=f"document-{source_id}",
            content_type=content_type,
            raw_content=document_text.encode("utf-8"),
        )
        chunks = self.ingestion_worker.ingest(source)
        logger.info("Ingested document into chunks", count=len(chunks), tenant_id=str(tenant_id))

        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))
                    for chunk in chunks:
                        embedding_vector = await self.embedder_policy.embed_text(chunk.text)
                        await conn.execute(
                            """
                            INSERT INTO knowledge_chunks (
                                id, tenant_id, agent_id, source_document_id, text, metadata_jsonb, embedding
                            ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                            """,
                            chunk.chunk_id,
                            tenant_id,
                            agent_id,
                            source_id,
                            chunk.text,
                            chunk.metadata,
                            str(embedding_vector) if embedding_vector else None,
                        )
            except Exception as exc:
                logger.warning("Failed to persist knowledge chunks", error=str(exc))

        return chunks
