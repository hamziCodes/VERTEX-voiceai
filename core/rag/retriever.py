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
        """Search knowledge base chunks for query (tenant isolated)."""
        tenant_chunks = self._mock_chunks.get(tenant_id, [])
        query_words = set(query.lower().split())

        # Simple keyword/vector match score for mock
        scored = []
        for chunk in tenant_chunks:
            chunk_words = set(chunk.text.lower().split())
            score = len(query_words.intersection(chunk_words))
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in scored[:top_k]]
