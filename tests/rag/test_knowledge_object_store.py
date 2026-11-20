from __future__ import annotations

from uuid import uuid4

import pytest

from core.storage.knowledge_objects import (
    KnowledgeStorageConfigurationError,
    LocalKnowledgeObjectStore,
    get_default_knowledge_object_store,
)


@pytest.mark.asyncio
async def test_local_store_round_trip_and_idempotent_delete(tmp_path) -> None:
    tenant_id = uuid4()
    store = LocalKnowledgeObjectStore(tmp_path, max_bytes=32)
    reference = await store.put(tenant_id, b"bounded", suffix=".txt")
    assert str(tenant_id) in reference
    assert await store.read(reference) == b"bounded"
    await store.delete(reference)
    await store.delete(reference)
    with pytest.raises(FileNotFoundError):
        await store.read(reference)


def test_protected_environment_refuses_local_fallback(monkeypatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.delenv("UCVE_KNOWLEDGE_S3_BUCKET", raising=False)
    with pytest.raises(KnowledgeStorageConfigurationError):
        get_default_knowledge_object_store()
