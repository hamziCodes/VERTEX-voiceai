from __future__ import annotations

from uuid import UUID

from core.rag.ingestion.parsers.base import ParsedDocument
from core.rag.models import ChunkConfig, KnowledgeBaseChunk


def chunk_structured_document(
    document: ParsedDocument,
    *,
    tenant_id: UUID,
    source_id: UUID,
    config: ChunkConfig | None = None,
) -> list[KnowledgeBaseChunk]:
    cfg = config or ChunkConfig()
    words_per_chunk = max(1, int(cfg.chunk_size_tokens * 0.75))
    overlap = min(words_per_chunk - 1, int(cfg.chunk_overlap_tokens * 0.75))
    step = max(1, words_per_chunk - overlap)
    chunks: list[KnowledgeBaseChunk] = []
    for section in document.sections:
        words = section.text.split()
        for offset in range(0, len(words), step):
            part = words[offset : offset + words_per_chunk]
            if not part:
                continue
            metadata = {
                "citation": section.citation,
                "word_offset": offset,
                "word_count": len(part),
            }
            chunks.append(
                KnowledgeBaseChunk(
                    tenant_id=tenant_id,
                    source_document_id=source_id,
                    text=" ".join(part),
                    metadata=metadata,
                )
            )
    return chunks
