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


@pytest.mark.asyncio
async def test_durable_claim_parse_chunk_and_restart(tmp_path) -> None:
    import psycopg

    from core.db.async_pg import AsyncDatabase
    from core.db.repos.knowledge_repo import PostgresKnowledgeRepository
    from core.rag.ingestion.validation import validate_upload
    from core.rag.ingestion.worker import IngestionWorker
    from core.storage.knowledge_objects import LocalKnowledgeObjectStore
    from infra.db.migrate import apply_migrations_async

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)
    tenant_id = uuid4()
    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        await connection.execute(
            "INSERT INTO tenants (id, name) VALUES (%s, %s)",
            (tenant_id, "phase10b-ingestion"),
        )
        await connection.commit()
    finally:
        await connection.close()

    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=2)
    await database.open()
    try:
        repository = PostgresKnowledgeRepository(database)
        base = await repository.create_knowledge_base(tenant_id, "Durable documents")
        content = b"The support desk opens at nine."
        validated = validate_upload("hours.txt", "text/plain", content)
        store = LocalKnowledgeObjectStore(tmp_path)
        reference = await store.put(tenant_id, content, suffix=".txt")
        source = await repository.create_source(
            tenant_id,
            base.knowledge_base_id,
            source_type="txt",
            display_name="hours.txt",
            media_type="text/plain",
            byte_count=len(content),
            checksum_sha256=validated.checksum_sha256,
            object_reference=reference,
        )
        worker = IngestionWorker(repository, store, worker_id="phase10b-test")
        assert await worker.process_next() == source.source_id
        assert await worker.process_next() is None
        completed = await repository.get_source(
            tenant_id, base.knowledge_base_id, source.source_id
        )
        assert completed.status.value == "embedding"
        assert completed.chunk_count == 1
    finally:
        await database.close()
