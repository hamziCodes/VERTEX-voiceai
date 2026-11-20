from __future__ import annotations

from uuid import uuid4

import pytest

from core.rag.embedders.base import EmbeddingBatch
from core.rag.models import KnowledgeBaseChunk
from core.rag.repository import InMemoryKnowledgeVectorRepository
from worker_jobs.kb_ingestion import KnowledgeEmbeddingWorker


class _DeterministicEmbedder:
    model_id = "deterministic-test"
    version = "v1"
    dimensions = 384

    async def embed(self, texts, *, purpose):
        vectors = []
        for index, _text in enumerate(texts):
            vector = [0.0] * 384
            vector[index % 384] = 1.0
            vectors.append(vector)
        return EmbeddingBatch(vectors, self.model_id, self.version, self.dimensions)


@pytest.mark.asyncio
async def test_embedding_job_completes_and_is_not_reclaimed_after_restart() -> None:
    repository = InMemoryKnowledgeVectorRepository()
    tenant_id = uuid4()
    base_id = uuid4()
    source_id = uuid4()
    repository.queue_source(
        tenant_id,
        base_id,
        source_id,
        revision=1,
        chunks=[
            KnowledgeBaseChunk(
                tenant_id=tenant_id,
                knowledge_base_id=base_id,
                source_document_id=source_id,
                revision=1,
                text="Opening hours are nine to five.",
            )
        ],
    )
    first = KnowledgeEmbeddingWorker(repository, _DeterministicEmbedder(), "worker-a")
    assert await first.process_next() == source_id
    restarted = KnowledgeEmbeddingWorker(
        repository, _DeterministicEmbedder(), "worker-b"
    )
    assert await restarted.process_next() is None
    chunk = repository.chunks[0]
    assert len(chunk.embedding) == 384
    assert chunk.embedding_model == "deterministic-test"
    assert repository.source_status(source_id) == "ready"


@pytest.mark.asyncio
async def test_embedding_dimension_failure_is_safe_and_retryable() -> None:
    class _WrongDimensionEmbedder(_DeterministicEmbedder):
        async def embed(self, texts, *, purpose):
            return EmbeddingBatch([[1.0, 0.0]], "wrong", "v1", 2)

    repository = InMemoryKnowledgeVectorRepository()
    tenant_id, base_id, source_id = uuid4(), uuid4(), uuid4()
    repository.queue_source(
        tenant_id,
        base_id,
        source_id,
        revision=1,
        chunks=[KnowledgeBaseChunk(tenant_id=tenant_id, text="text")],
    )
    worker = KnowledgeEmbeddingWorker(repository, _WrongDimensionEmbedder(), "worker")
    assert await worker.process_next() == source_id
    assert repository.source_status(source_id) == "failed"
    assert repository.failure_code(source_id) == "embedding_dimension_mismatch"
    repository.retry(source_id)
    assert repository.source_status(source_id) == "embedding"
