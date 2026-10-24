"""PDF Document Chunker — 400 token chunk size, 64 token overlap default."""

from __future__ import annotations

from uuid import UUID

from core.rag.models import ChunkConfig, KnowledgeBaseChunk


def chunk_pdf_text(
    text: str, tenant_id: UUID, config: ChunkConfig | None = None
) -> list[KnowledgeBaseChunk]:
    """Chunk PDF document text using 400 token chunk size & 64 token overlap."""
    cfg = config or ChunkConfig()
    words = text.split()
    if not words:
        return []

    # Approximate ~0.75 words/token -> 400 tokens ≈ 300 words
    words_per_chunk = int(cfg.chunk_size_tokens * 0.75)
    overlap_words = int(cfg.chunk_overlap_tokens * 0.75)
    step = max(1, words_per_chunk - overlap_words)

    chunks: list[KnowledgeBaseChunk] = []
    for i in range(0, len(words), step):
        chunk_words = words[i : i + words_per_chunk]
        chunk_text = " ".join(chunk_words)
        chunks.append(
            KnowledgeBaseChunk(
                tenant_id=tenant_id,
                text=chunk_text,
                metadata={"source": "pdf", "word_count": len(chunk_words)},
            )
        )
    return chunks
