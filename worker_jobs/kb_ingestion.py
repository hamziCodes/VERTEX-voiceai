"""Compatibility entry point for bounded knowledge document parsing."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core.observability.logging import get_logger
from core.rag.ingestion.worker import IngestionWorker
from core.rag.models import KnowledgeBaseChunk, KnowledgeBaseSource

logger = get_logger("ucve.jobs.kb_ingestion")


class KBIngestionJob:
    """Parse documents into unembedded chunks; Phase 10C owns embeddings."""

    def __init__(
        self, db_pool: Any | None = None, compliance_tier: str = "standard"
    ) -> None:
        self.db_pool = db_pool
        self.compliance_tier = compliance_tier
        self.ingestion_worker = IngestionWorker()

    async def process_document(
        self,
        tenant_id: UUID,
        source_id: UUID,
        document_text: str,
        content_type: str = "text/plain",
        agent_id: UUID | None = None,
    ) -> list[KnowledgeBaseChunk]:
        """Parse bounded text without pretending embeddings were persisted."""
        del agent_id
        suffix = {
            "application/json": ".json",
            "text/markdown": ".md",
            "text/csv": ".csv",
        }.get(content_type, ".txt")
        source_type = "faq_list" if content_type == "application/json" else content_type
        source = KnowledgeBaseSource(
            source_id=source_id,
            tenant_id=tenant_id,
            source_type=source_type,
            source_uri=f"document-{source_id}{suffix}",
        )
        chunks = await self.ingestion_worker.ingest_source(
            source, document_text.encode("utf-8")
        )
        logger.info(
            "Parsed document into unembedded chunks",
            count=len(chunks),
            tenant_id=str(tenant_id),
        )
        return chunks
