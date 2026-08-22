"""Knowledge Ingestion Worker — Ingests PDF/FAQ sources into pgvector store."""

from __future__ import annotations

from uuid import UUID

from core.rag.ingestion.chunkers.faq import chunk_faq_items
from core.rag.ingestion.chunkers.pdf import chunk_pdf_text
from core.rag.models import ChunkConfig, KnowledgeBaseChunk, KnowledgeBaseSource


class IngestionWorker:
    """Async background worker processing document sources into KnowledgeBaseChunks."""

    def __init__(self, chunk_config: ChunkConfig | None = None) -> None:
        self.config = chunk_config or ChunkConfig()
        self.ingested_chunks: list[KnowledgeBaseChunk] = []

    async def ingest_source(self, source: KnowledgeBaseSource, content_raw: Any) -> list[KnowledgeBaseChunk]:
        """Process document content according to source_type."""
        chunks: list[KnowledgeBaseChunk] = []

        if source.source_type == "pdf_upload":
            chunks = chunk_pdf_text(str(content_raw), tenant_id=source.tenant_id, config=self.config)
        elif source.source_type == "faq_list":
            if isinstance(content_raw, list):
                chunks = chunk_faq_items(content_raw, tenant_id=source.tenant_id)
        else:
            chunks = [
                KnowledgeBaseChunk(
                    tenant_id=source.tenant_id,
                    text=str(content_raw),
                    metadata={"source": source.source_type},
                )
            ]

        self.ingested_chunks.extend(chunks)
        return chunks
