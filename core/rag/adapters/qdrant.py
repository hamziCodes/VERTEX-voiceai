"""Qdrant External Vector DB Adapter Stub [LATER]."""

from __future__ import annotations

from uuid import UUID

from core.rag.models import KnowledgeBaseChunk
from core.rag.retriever import RAGRetriever


class QdrantRetrieverStub(RAGRetriever):
    """Optional Qdrant vector DB adapter stub."""

    def __init__(self, endpoint: str = "http://localhost:6333") -> None:
        self.endpoint = endpoint

    async def retrieve(
        self,
        query: str,
        tenant_id: UUID,
        top_k: int = 3,
        *,
        agent_id: UUID | None = None,
        agent_config_version: int | None = None,
        knowledge_base_id: UUID | None = None,
        revision: int | None = None,
    ) -> list[KnowledgeBaseChunk]:
        del (
            query,
            tenant_id,
            top_k,
            agent_id,
            agent_config_version,
            knowledge_base_id,
            revision,
        )
        return []
