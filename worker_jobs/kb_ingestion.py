"""Compatibility entry point for bounded knowledge document parsing."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from core.observability.logging import get_logger
from core.rag.embedders.base import (
    EXPECTED_EMBEDDING_DIMENSIONS,
    EmbeddingBatch,
    EmbeddingError,
    EmbeddingPurpose,
    TextEmbedder,
)
from core.rag.ingestion.worker import IngestionWorker
from core.rag.models import KnowledgeBaseChunk, KnowledgeBaseSource
from core.rag.repository import KnowledgeVectorError

logger = get_logger("ucve.jobs.kb_ingestion")


class KnowledgeEmbeddingWorker:
    """Claim parsed sources, embed chunks off-loop, and complete them atomically."""

    def __init__(self, repository: Any, embedder: TextEmbedder, worker_id: str) -> None:
        self.repository = repository
        self.embedder = embedder
        self.worker_id = worker_id

    async def process_next(self) -> UUID | None:
        work = await _resolve(self.repository.claim_embedding_job(self.worker_id))
        if work is None:
            return None
        try:
            if not work.chunks:
                raise KnowledgeVectorError(
                    "embedding_chunks_missing", "Embedding job has no chunks."
                )
            vectors: list[list[float]] = []
            for start in range(0, len(work.chunks), 64):
                batch = await self.embedder.embed(
                    [chunk.text for chunk in work.chunks[start : start + 64]],
                    purpose=EmbeddingPurpose.PASSAGE,
                )
                if batch.dimensions != EXPECTED_EMBEDDING_DIMENSIONS:
                    raise KnowledgeVectorError(
                        "embedding_dimension_mismatch",
                        "Embedding adapter returned the wrong dimensions.",
                    )
                if (
                    batch.model_id != self.embedder.model_id
                    or batch.version != self.embedder.version
                ):
                    raise KnowledgeVectorError(
                        "embedding_model_mismatch",
                        "Embedding adapter metadata changed during the job.",
                    )
                vectors.extend(batch.vectors)
            completed = EmbeddingBatch(
                vectors=vectors,
                model_id=self.embedder.model_id,
                version=self.embedder.version,
                dimensions=self.embedder.dimensions,
            )
            await _resolve(self.repository.complete_embeddings(work, completed))
        except (EmbeddingError, KnowledgeVectorError) as exc:
            await _resolve(
                self.repository.fail_embedding(
                    work, code=exc.code, message=exc.safe_message
                )
            )
        except Exception:
            await _resolve(
                self.repository.fail_embedding(
                    work,
                    code="embedding_internal_error",
                    message="Embedding processing failed unexpectedly.",
                )
            )
        return cast(UUID, work.source_id)


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


async def _resolve(value: Any) -> Any:
    return await value if hasattr(value, "__await__") else value
