from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


class _SemanticFixtureEmbedder:
    model_id = "phase10c-test-384"
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


async def _add_source(repository, store, parsing_worker, tenant_id, base_id, text):
    from core.rag.ingestion.validation import validate_upload

    content = text.encode()
    validated = validate_upload("policy.txt", "text/plain", content)
    reference = await store.put(tenant_id, content, suffix=".txt")
    source = await repository.create_source(
        tenant_id,
        base_id,
        source_type="txt",
        display_name="policy.txt",
        media_type="text/plain",
        byte_count=len(content),
        checksum_sha256=validated.checksum_sha256,
        object_reference=reference,
    )
    assert await parsing_worker.process_next() == source.source_id
    return source


async def _process_until(worker, source_id):
    for _attempt in range(10):
        processed = await worker.process_next()
        if processed == source_id:
            return processed
        if processed is None:
            break
    raise AssertionError("Target embedding source was not claimed.")


@pytest.mark.asyncio
async def test_pgvector_agent_scope_revision_switch_and_restart(tmp_path) -> None:
    import psycopg

    from core.db.async_pg import AsyncDatabase
    from core.db.repos.knowledge_repo import PostgresKnowledgeRepository
    from core.rag.ingestion.worker import IngestionWorker
    from core.rag.repository import PostgresKnowledgeVectorRepository
    from core.rag.retriever import PgVectorRetriever, RetrievalScopeError
    from core.storage.knowledge_objects import LocalKnowledgeObjectStore
    from infra.db.migrate import apply_migrations_async
    from worker_jobs.kb_ingestion import KnowledgeEmbeddingWorker

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)
    tenant_id, other_tenant, agent_id, unbound_agent = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    version_1, version_2 = uuid4(), uuid4()
    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        await connection.execute(
            "INSERT INTO tenants (id, name) VALUES (%s, %s), (%s, %s)",
            (tenant_id, "phase10c-a", other_tenant, "phase10c-b"),
        )
        await connection.execute(
            "INSERT INTO agent_configs "
            "(agent_id, tenant_id, name, current_version, draft_data) "
            "VALUES (%s, %s, %s, 2, %s::jsonb), (%s, %s, %s, 0, %s::jsonb)",
            (
                agent_id,
                tenant_id,
                "bound-agent",
                "{}",
                unbound_agent,
                tenant_id,
                "unbound-agent",
                "{}",
            ),
        )
        await connection.execute(
            "INSERT INTO agent_config_versions "
            "(version_id, agent_id, tenant_id, version, config_snapshot) "
            "VALUES (%s, %s, %s, 1, %s::jsonb), (%s, %s, %s, 2, %s::jsonb)",
            (
                version_1,
                agent_id,
                tenant_id,
                "{}",
                version_2,
                agent_id,
                tenant_id,
                "{}",
            ),
        )
        await connection.commit()
    finally:
        await connection.close()

    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=3)
    await database.open()
    try:
        knowledge = PostgresKnowledgeRepository(database)
        vectors = PostgresKnowledgeVectorRepository(database)
        store = LocalKnowledgeObjectStore(tmp_path)
        parser = IngestionWorker(knowledge, store, worker_id="parser")
        embedder = _SemanticFixtureEmbedder()
        embedding_worker = KnowledgeEmbeddingWorker(vectors, embedder, "embedder-a")
        base = await knowledge.create_knowledge_base(tenant_id, "Policies")

        first = await _add_source(
            knowledge,
            store,
            parser,
            tenant_id,
            base.knowledge_base_id,
            "Refund requests are accepted within fourteen days.",
        )
        assert (
            await _process_until(embedding_worker, first.source_id) == first.source_id
        )
        restarted = KnowledgeEmbeddingWorker(vectors, embedder, "embedder-b")
        assert await restarted.process_next() is None
        await knowledge.activate_knowledge_base(tenant_id, base.knowledge_base_id)
        await knowledge.record_binding(
            tenant_id, agent_id, 1, base.knowledge_base_id, 1
        )
        retriever = PgVectorRetriever(repository=vectors, embedder=embedder)
        revision_one = await retriever.retrieve(
            "refund rules",
            tenant_id,
            agent_id=agent_id,
            knowledge_base_id=base.knowledge_base_id,
            revision=1,
        )
        assert "fourteen days" in revision_one[0].text
        assert revision_one[0].score == pytest.approx(1.0)
        assert revision_one[0].citation
        version_one = await retriever.retrieve(
            "refund rules",
            tenant_id,
            agent_id=agent_id,
            agent_config_version=1,
            knowledge_base_id=base.knowledge_base_id,
        )
        assert "fourteen days" in version_one[0].text

        with pytest.raises(RetrievalScopeError):
            await retriever.retrieve(
                "refund rules",
                tenant_id,
                agent_id=unbound_agent,
                knowledge_base_id=base.knowledge_base_id,
                revision=1,
            )
        with pytest.raises(RetrievalScopeError):
            await retriever.retrieve(
                "refund rules",
                other_tenant,
                agent_id=agent_id,
                knowledge_base_id=base.knowledge_base_id,
                revision=1,
            )

        second = await _add_source(
            knowledge,
            store,
            parser,
            tenant_id,
            base.knowledge_base_id,
            "Refund requests are accepted within thirty days.",
        )
        assert (
            await _process_until(embedding_worker, second.source_id) == second.source_id
        )
        await knowledge.activate_knowledge_base(tenant_id, base.knowledge_base_id)
        await knowledge.record_binding(
            tenant_id, agent_id, 2, base.knowledge_base_id, 2
        )
        revision_two = await retriever.retrieve(
            "refund rules",
            tenant_id,
            agent_id=agent_id,
            knowledge_base_id=base.knowledge_base_id,
            revision=2,
        )
        assert "thirty days" in revision_two[0].text
        version_two = await retriever.retrieve(
            "refund rules",
            tenant_id,
            agent_id=agent_id,
            agent_config_version=2,
            knowledge_base_id=base.knowledge_base_id,
        )
        assert "thirty days" in version_two[0].text
        pinned_old = await retriever.retrieve(
            "refund rules",
            tenant_id,
            agent_id=agent_id,
            knowledge_base_id=base.knowledge_base_id,
            revision=1,
        )
        assert "fourteen days" in pinned_old[0].text
    finally:
        await database.close()
