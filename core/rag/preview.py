"""Bounded operator preview retrieval for one tenant knowledge revision."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from core.rag.embedder_policy import EmbedderPolicy
from core.rag.embedders.base import (
    EXPECTED_EMBEDDING_DIMENSIONS,
    EmbeddingPurpose,
    TextEmbedder,
)
from core.rag.models import KnowledgeBaseChunk
from core.rag.repository import KnowledgeVectorError


class KnowledgePreviewService:
    def __init__(self, repository: Any, embedder: TextEmbedder | None = None) -> None:
        self.repository = repository
        self.embedder = embedder

    async def preview(
        self,
        *,
        query: str,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        revision: int,
        top_k: int,
    ) -> list[KnowledgeBaseChunk]:
        normalized = query.strip()
        if not normalized:
            return []
        embedder = self.embedder or EmbedderPolicy.create_from_environment(
            compliance_tier="standard"
        )
        self.embedder = embedder
        batch = await embedder.embed(
            [normalized], purpose=EmbeddingPurpose.QUERY
        )
        if (
            batch.dimensions != EXPECTED_EMBEDDING_DIMENSIONS
            or len(batch.vectors) != 1
            or len(batch.vectors[0]) != EXPECTED_EMBEDDING_DIMENSIONS
        ):
            raise KnowledgeVectorError(
                "embedding_dimension_mismatch",
                "Query embedding dimension is invalid.",
            )
        return cast(
            list[KnowledgeBaseChunk],
            await self.repository.preview_search(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                revision=revision,
                query_vector=batch.vectors[0],
                embedding_model=batch.model_id,
                embedding_version=batch.version,
                top_k=max(1, min(top_k, 8)),
            ),
        )
