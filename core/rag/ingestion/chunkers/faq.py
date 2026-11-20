"""FAQ Document Chunker — Preserves Question & Answer pairs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core.rag.models import KnowledgeBaseChunk


def chunk_faq_items(
    faq_list: list[dict[str, Any]], tenant_id: UUID
) -> list[KnowledgeBaseChunk]:
    """Convert list of FAQ dict items ({question, answer}) into KnowledgeBaseChunks."""
    chunks: list[KnowledgeBaseChunk] = []
    for item in faq_list:
        q = item.get("question", "")
        a = item.get("answer", "")
        text = f"Q: {q}\nA: {a}"
        chunks.append(
            KnowledgeBaseChunk(
                tenant_id=tenant_id,
                text=text,
                metadata={"source": "faq", "question": q},
            )
        )
    return chunks
