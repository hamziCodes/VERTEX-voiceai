"""Agent-scoped pgvector retrieval with explicit local-test compatibility."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, cast
from uuid import UUID

from core.rag.embedders.base import (
    EXPECTED_EMBEDDING_DIMENSIONS,
    EmbeddingPurpose,
    TextEmbedder,
)
from core.rag.models import KnowledgeBaseChunk
from core.rag.repository import KnowledgeVectorError
from core.runtime.env import is_protected_environment


class RetrievalScopeError(KnowledgeVectorError):
    pass


class RAGRetriever(ABC):
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        tenant_id: UUID,
        top_k: int = 3,
        *,
        agent_id: UUID | None = None,
        knowledge_base_id: UUID | None = None,
        revision: int | None = None,
    ) -> list[KnowledgeBaseChunk]: ...


class PgVectorRetriever(RAGRetriever):
    """Embed a query and search a pinned agent-bound knowledge revision."""

    def __init__(
        self,
        db_pool: Any | None = None,
        *,
        repository: Any | None = None,
        embedder: TextEmbedder | None = None,
    ) -> None:
        if db_pool is not None and repository is None:
            raise TypeError(
                "Use PostgresKnowledgeVectorRepository instead of a raw pool."
            )
        self._protected_unconfigured = repository is None and is_protected_environment()
        self.repository = repository
        self.embedder = embedder
        self._test_chunks: dict[UUID, list[KnowledgeBaseChunk]] = {}

    def seed_chunks(self, tenant_id: UUID, chunks: list[KnowledgeBaseChunk]) -> None:
        """Seed the explicit local-test adapter."""
        if self.repository is not None:
            raise RuntimeError("Cannot seed a durable retriever.")
        self._test_chunks.setdefault(tenant_id, []).extend(chunks)

    async def retrieve(
        self,
        query: str,
        tenant_id: UUID,
        top_k: int = 3,
        *,
        agent_id: UUID | None = None,
        knowledge_base_id: UUID | None = None,
        revision: int | None = None,
    ) -> list[KnowledgeBaseChunk]:
        normalized = query.strip()
        if not normalized:
            return []
        if self._protected_unconfigured:
            raise RuntimeError(
                "Protected retrieval requires a durable vector repository."
            )
        if self.repository is None:
            return self._retrieve_test_chunks(normalized, tenant_id, top_k)
        if self.embedder is None:
            raise RuntimeError("Durable retrieval requires an embedding adapter.")
        if agent_id is None or knowledge_base_id is None or revision is None:
            raise RetrievalScopeError(
                "knowledge_scope_required",
                "Agent, knowledge base, and revision are required.",
            )
        batch = await self.embedder.embed([normalized], purpose=EmbeddingPurpose.QUERY)
        if (
            batch.dimensions != EXPECTED_EMBEDDING_DIMENSIONS
            or len(batch.vectors) != 1
            or len(batch.vectors[0]) != EXPECTED_EMBEDDING_DIMENSIONS
        ):
            raise KnowledgeVectorError(
                "embedding_dimension_mismatch",
                "Query embedding dimension is invalid.",
            )
        try:
            return cast(
                list[KnowledgeBaseChunk],
                await self.repository.search(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    knowledge_base_id=knowledge_base_id,
                    revision=revision,
                    query_vector=batch.vectors[0],
                    embedding_model=batch.model_id,
                    embedding_version=batch.version,
                    top_k=top_k,
                ),
            )
        except KnowledgeVectorError as exc:
            if exc.code in {"knowledge_binding_required", "knowledge_scope_required"}:
                raise RetrievalScopeError(exc.code, exc.safe_message) from exc
            raise

    def _retrieve_test_chunks(
        self, query: str, tenant_id: UUID, top_k: int
    ) -> list[KnowledgeBaseChunk]:
        query_words = set(query.casefold().split())
        scored = [
            (len(query_words.intersection(chunk.text.casefold().split())), chunk)
            for chunk in self._test_chunks.get(tenant_id, [])
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _score, chunk in scored[: max(1, min(top_k, 10))]]
