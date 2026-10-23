from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def knowledge_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")

    from control_plane.app import app
    from control_plane.routes.knowledge_bases import get_knowledge_repo
    from core.db.repos.knowledge_repo import InMemoryKnowledgeRepository

    repository = InMemoryKnowledgeRepository()
    app.dependency_overrides[get_knowledge_repo] = lambda: repository
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.pop(get_knowledge_repo, None)


def _key(client: TestClient, tenant_id: UUID, *scopes: str) -> str:
    from control_plane.app import app

    raw, _ = app.state.api_keys.generate_api_key(
        str(tenant_id),
        "knowledge-test",
        scopes=list(scopes),
        role="tenant_editor",
        subject_id="knowledge-test-service",
    )
    return raw


def _headers(client: TestClient, tenant_id: UUID, *scopes: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_key(client, tenant_id, *scopes)}"}


def test_create_and_list_knowledge_bases_are_tenant_scoped(knowledge_client) -> None:
    client, _repository = knowledge_client
    tenant_a = uuid4()
    tenant_b = uuid4()
    headers_a = _headers(client, tenant_a, "knowledge:read", "knowledge:write")
    headers_b = _headers(client, tenant_b, "knowledge:read")

    created = client.post(
        "/v1/knowledge-bases", headers=headers_a, json={"name": "Support docs"}
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["tenant_id"] == str(tenant_a)
    assert payload["status"] == "draft"
    assert payload["source_count"] == 0
    assert payload["ready_source_count"] == 0
    assert payload["total_chunks"] == 0
    assert (
        client.get("/v1/knowledge-bases", headers=headers_a).json()[0][
            "knowledge_base_id"
        ]
        == payload["knowledge_base_id"]
    )
    assert client.get("/v1/knowledge-bases", headers=headers_b).json() == []
    assert (
        client.get(
            f"/v1/knowledge-bases/{payload['knowledge_base_id']}",
            headers=headers_b,
        ).status_code
        == 404
    )


def test_activation_requires_ready_sources_and_reports_real_counts(
    knowledge_client,
) -> None:
    client, repository = knowledge_client
    tenant_id = uuid4()
    headers = _headers(client, tenant_id, "knowledge:read", "knowledge:write")
    created = client.post(
        "/v1/knowledge-bases", headers=headers, json={"name": "Policies"}
    ).json()
    kb_id = UUID(created["knowledge_base_id"])

    denied = client.post(f"/v1/knowledge-bases/{kb_id}/activate", headers=headers)
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "knowledge_not_ready"

    source = repository.create_source(
        tenant_id,
        kb_id,
        source_type="pdf",
        display_name="policy.pdf",
        media_type="application/pdf",
        byte_count=128,
        checksum_sha256="a" * 64,
        object_reference="knowledge/test/policy.pdf",
    )
    repository.mark_source_ready(tenant_id, kb_id, source.source_id, chunk_count=7)

    source_status = client.get(
        f"/v1/knowledge-bases/{kb_id}/sources/{source.source_id}", headers=headers
    )
    assert source_status.status_code == 200
    assert "object_reference" not in source_status.json()

    activated = client.post(f"/v1/knowledge-bases/{kb_id}/activate", headers=headers)
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert activated.json()["active_revision"] == 1
    assert activated.json()["ready_source_count"] == 1
    assert activated.json()["total_chunks"] == 7

    status = client.get(f"/v1/knowledge-bases/status/{tenant_id}", headers=headers)
    assert status.status_code == 200
    assert status.json() == {
        "tenant_id": str(tenant_id),
        "status": "ready",
        "knowledge_base_count": 1,
        "ready_knowledge_base_count": 1,
        "source_count": 1,
        "ready_source_count": 1,
        "total_chunks": 7,
    }


def test_failed_source_retry_is_idempotent_and_tenant_bound(knowledge_client) -> None:
    client, repository = knowledge_client
    tenant_id = uuid4()
    other_tenant = uuid4()
    headers = _headers(client, tenant_id, "knowledge:read", "knowledge:write")
    other_headers = _headers(client, other_tenant, "knowledge:read", "knowledge:write")
    kb_id = UUID(
        client.post(
            "/v1/knowledge-bases", headers=headers, json={"name": "FAQ"}
        ).json()["knowledge_base_id"]
    )
    source = repository.create_source(
        tenant_id,
        kb_id,
        source_type="faq",
        display_name="FAQ",
        media_type="application/json",
        byte_count=32,
        checksum_sha256="b" * 64,
        object_reference="knowledge/test/faq.json",
    )
    repository.mark_source_failed(
        tenant_id, kb_id, source.source_id, error_code="parser_timeout"
    )

    assert (
        client.post(
            f"/v1/knowledge-bases/{kb_id}/sources/{source.source_id}/retry",
            headers=other_headers,
        ).status_code
        == 404
    )
    first = client.post(
        f"/v1/knowledge-bases/{kb_id}/sources/{source.source_id}/retry",
        headers=headers,
    )
    second = client.post(
        f"/v1/knowledge-bases/{kb_id}/sources/{source.source_id}/retry",
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "queued"
    assert second.json()["job_id"] == first.json()["job_id"]
    assert second.json()["attempt"] == first.json()["attempt"]


def test_pending_revision_does_not_disable_active_knowledge(knowledge_client) -> None:
    _client, repository = knowledge_client
    tenant_id = uuid4()
    base = repository.create_knowledge_base(tenant_id, "Always available")
    first = repository.create_source(
        tenant_id,
        base.knowledge_base_id,
        source_type="txt",
        display_name="v1.txt",
        media_type="text/plain",
        byte_count=2,
        checksum_sha256="1" * 64,
        object_reference="knowledge/test/v1.txt",
    )
    repository.mark_source_ready(
        tenant_id, base.knowledge_base_id, first.source_id, chunk_count=2
    )
    repository.activate_knowledge_base(tenant_id, base.knowledge_base_id)

    second = repository.create_source(
        tenant_id,
        base.knowledge_base_id,
        source_type="txt",
        display_name="v2.txt",
        media_type="text/plain",
        byte_count=2,
        checksum_sha256="2" * 64,
        object_reference="knowledge/test/v2.txt",
    )
    repository.mark_source_failed(
        tenant_id,
        base.knowledge_base_id,
        second.source_id,
        error_code="parser_timeout",
    )

    current = repository.get_knowledge_base(tenant_id, base.knowledge_base_id)
    assert current.status.value == "active"
    assert current.active_revision == 1
    assert current.total_chunks == 2


def test_binding_active_knowledge_publishes_new_agent_version(
    knowledge_client,
) -> None:
    client, repository = knowledge_client
    tenant_id = uuid4()
    headers = _headers(
        client,
        tenant_id,
        "knowledge:read",
        "knowledge:write",
        "agent:read",
        "agent:write",
    )
    agent = client.post("/v1/agents", headers=headers, json={"name": "Agent"})
    assert agent.status_code == 201
    agent_id = agent.json()["agent_id"]
    kb_id = UUID(
        client.post(
            "/v1/knowledge-bases", headers=headers, json={"name": "Catalog"}
        ).json()["knowledge_base_id"]
    )
    source = repository.create_source(
        tenant_id,
        kb_id,
        source_type="csv",
        display_name="catalog.csv",
        media_type="text/csv",
        byte_count=64,
        checksum_sha256="c" * 64,
        object_reference="knowledge/test/catalog.csv",
    )
    repository.mark_source_ready(tenant_id, kb_id, source.source_id, chunk_count=3)
    client.post(f"/v1/knowledge-bases/{kb_id}/activate", headers=headers)

    bound = client.post(f"/v1/knowledge-bases/{kb_id}/bind/{agent_id}", headers=headers)

    assert bound.status_code == 200
    assert bound.json()["agent_id"] == agent_id
    assert bound.json()["knowledge_base_id"] == str(kb_id)
    assert bound.json()["knowledge_revision"] == 1
    assert bound.json()["agent_config_version"] == 1
    published = client.get(f"/v1/agents/{agent_id}/versions/1", headers=headers)
    assert published.status_code == 200
    assert published.json()["knowledge_bases"] == [{"id": str(kb_id), "revision": 1}]


def test_binding_requires_agent_write_and_returns_404_for_missing_agent(
    knowledge_client,
) -> None:
    client, repository = knowledge_client
    tenant_id = uuid4()
    full_headers = _headers(
        client,
        tenant_id,
        "knowledge:read",
        "knowledge:write",
        "agent:write",
    )
    knowledge_only = _headers(client, tenant_id, "knowledge:read", "knowledge:write")
    kb_id = UUID(
        client.post(
            "/v1/knowledge-bases", headers=full_headers, json={"name": "Secure"}
        ).json()["knowledge_base_id"]
    )
    source = repository.create_source(
        tenant_id,
        kb_id,
        source_type="txt",
        display_name="secure.txt",
        media_type="text/plain",
        byte_count=12,
        checksum_sha256="d" * 64,
        object_reference="knowledge/test/secure.txt",
    )
    repository.mark_source_ready(tenant_id, kb_id, source.source_id, chunk_count=1)
    client.post(f"/v1/knowledge-bases/{kb_id}/activate", headers=full_headers)
    missing_agent = uuid4()

    assert (
        client.post(
            f"/v1/knowledge-bases/{kb_id}/bind/{missing_agent}",
            headers=knowledge_only,
        ).status_code
        == 403
    )
    response = client.post(
        f"/v1/knowledge-bases/{kb_id}/bind/{missing_agent}",
        headers=full_headers,
    )
    assert response.status_code == 404
