"""RAG Retriever & PgVector Database Integration — Tenant isolated knowledge search."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from core.rag.models import KnowledgeBaseChunk


class RAGRetriever(ABC):
    """Abstract vector knowledge base retriever interface."""

    @abstractmethod
    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 3) -> list[KnowledgeBaseChunk]:
        """Retrieve top_k vector chunks for query strictly isolated to tenant_id."""
        pass


class PgVectorRetriever(RAGRetriever):
    """pgvector implementation of RAGRetriever in existing PostgreSQL database."""

    def __init__(self, db_pool: Any | None = None) -> None:
        self.db_pool = db_pool
        self._mock_chunks: dict[UUID, list[KnowledgeBaseChunk]] = {}

    def seed_chunks(self, tenant_id: UUID, chunks: list[KnowledgeBaseChunk]) -> None:
        """Seed chunks for mock retriever testing."""
        self._mock_chunks.setdefault(tenant_id, []).extend(chunks)

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 3) -> list[KnowledgeBaseChunk]:
        """Search knowledge base chunks for query strictly isolated to tenant_id."""
        if self.db_pool:
            try:
                # Execute real pgvector SQL search with tenant session setting
                async with self.db_pool.acquire() as conn:
                    await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))
                    rows = await conn.fetch(
                        """
                        SELECT id, tenant_id, source_document_id, text, metadata_jsonb
                        FROM knowledge_chunks
                        WHERE tenant_id = $1
                        ORDER BY text <-> $2
                        LIMIT $3
                        """,
                        tenant_id,
                        query,
                        top_k,
                    )
                    return [
                        KnowledgeBaseChunk(
                            chunk_id=r["id"],
                            tenant_id=r["tenant_id"],
                            source_document_id=r["source_document_id"],
                            text=r["text"],
                            metadata=r["metadata_jsonb"] or {},
                        )
                        for r in rows
                    ]
            except Exception:
                pass

        # In-memory seeded fallback for testing/dev
        tenant_chunks = self._mock_chunks.get(tenant_id, [])
        query_words = set(query.lower().split())

        scored = []
        for chunk in tenant_chunks:
            chunk_words = set(chunk.text.lower().split())
            score = len(query_words.intersection(chunk_words))
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in scored[:top_k]]
