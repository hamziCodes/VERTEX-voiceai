from __future__ import annotations

from uuid import uuid4

import pytest

from core.rag.models import KnowledgeBaseChunk
from core.rag.repository import InMemoryKnowledgeVectorRepository
from core.rag.retriever import PgVectorRetriever, RetrievalScopeError
from core.rag.speculative import SpeculativeRetrieval


class _QueryEmbedder:
    model_id = "test-384"
    version = "v1"
    dimensions = 384

    async def embed(self, texts, *, purpose):
        from core.rag.embedders.base import EmbeddingBatch

        vectors = []
        for text in texts:
            vector = [0.0] * 384
            vector[0 if "refund" in text.casefold() else 1] = 1.0
            vectors.append(vector)
        return EmbeddingBatch(vectors, self.model_id, self.version, self.dimensions)


@pytest.mark.asyncio
async def test_retrieval_requires_agent_binding_and_pinned_revision() -> None:
    repository = InMemoryKnowledgeVectorRepository()
    tenant_id = uuid4()
    other_tenant = uuid4()
    agent_id = uuid4()
    base_id = uuid4()
    source_id = uuid4()
    repository.add_chunk(
        KnowledgeBaseChunk(
            tenant_id=tenant_id,
            knowledge_base_id=base_id,
            source_document_id=source_id,
            revision=2,
            text="Refunds are available within fourteen days.",
            embedding=[1.0] + [0.0] * 383,
            metadata={"citation": {"page": 3}},
            embedding_model="test-384",
            embedding_version="v1",
        )
    )
    repository.add_chunk(
        KnowledgeBaseChunk(
            tenant_id=other_tenant,
            knowledge_base_id=base_id,
            source_document_id=uuid4(),
            revision=2,
            text="Other tenant secret",
            embedding=[1.0] + [0.0] * 383,
            embedding_model="test-384",
            embedding_version="v1",
        )
    )
    retriever = PgVectorRetriever(repository=repository, embedder=_QueryEmbedder())

    with pytest.raises(RetrievalScopeError, match="knowledge_binding_required"):
        await retriever.retrieve(
            "refund",
            tenant_id,
            agent_id=agent_id,
            knowledge_base_id=base_id,
            revision=2,
        )

    repository.bind(tenant_id, agent_id, base_id, revision=2)
    hits = await retriever.retrieve(
        "refund",
        tenant_id,
        agent_id=agent_id,
        knowledge_base_id=base_id,
        revision=2,
    )
    assert [hit.text for hit in hits] == ["Refunds are available within fourteen days."]
    assert hits[0].citation == {"page": 3}
    assert hits[0].score == pytest.approx(1.0)

    with pytest.raises(RetrievalScopeError, match="knowledge_binding_required"):
        await retriever.retrieve(
            "refund",
            tenant_id,
            agent_id=agent_id,
            knowledge_base_id=base_id,
            revision=1,
        )


@pytest.mark.asyncio
async def test_durable_retriever_never_silently_falls_back() -> None:
    class _BrokenRepository:
        async def search(self, **_kwargs):
            raise RuntimeError("database unavailable")

    retriever = PgVectorRetriever(
        repository=_BrokenRepository(), embedder=_QueryEmbedder()
    )
    with pytest.raises(RuntimeError, match="database unavailable"):
        await retriever.retrieve(
            "refund",
            uuid4(),
            agent_id=uuid4(),
            knowledge_base_id=uuid4(),
            revision=1,
        )


@pytest.mark.asyncio
async def test_protected_unconfigured_retrieval_fails_on_use(monkeypatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "production")
    retriever = PgVectorRetriever()
    with pytest.raises(RuntimeError, match="durable vector repository"):
        await retriever.retrieve("refund", uuid4())


@pytest.mark.asyncio
async def test_speculative_results_are_invalidated_when_revision_changes() -> None:
    class _RecordingRetriever:
        def __init__(self) -> None:
            self.calls = 0

        async def retrieve(self, query, tenant_id, top_k=3, **scope):
            self.calls += 1
            return [KnowledgeBaseChunk(tenant_id=tenant_id, text=query)]

    recording = _RecordingRetriever()
    speculative = SpeculativeRetrieval(recording)
    tenant_id, agent_id, base_id = uuid4(), uuid4(), uuid4()
    await speculative.speculate(
        "refund policy",
        tenant_id,
        agent_id=agent_id,
        knowledge_base_id=base_id,
        revision=1,
    )
    await speculative.reconcile(
        "refund policy",
        tenant_id,
        agent_id=agent_id,
        knowledge_base_id=base_id,
        revision=2,
    )
    assert recording.calls == 2
