from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    with TestClient(app) as test_client:
        yield test_client
    if hasattr(app.state, "oidc_provider"):
        delattr(app.state, "oidc_provider")


def _key(
    client: TestClient,
    tenant_id: str,
    *,
    scopes: list[str],
    role: str,
) -> str:
    from control_plane.app import app

    raw, _ = app.state.api_keys.generate_api_key(
        tenant_id,
        "route-test",
        scopes=scopes,
        role=role,
        subject_id="route-test-service",
    )
    return raw


def test_route_policy_classifies_every_management_route(client: TestClient) -> None:
    from control_plane.app import app
    from control_plane.auth.route_policy import ROUTE_POLICIES

    management_prefixes = tuple(
        policy.path_prefix
        for policy in ROUTE_POLICIES
        if policy.auth_class == "management"
    )
    assert all(
        policy.permission and ":" in policy.permission
        for policy in ROUTE_POLICIES
        if policy.auth_class == "management"
    )
    registered = {
        path
        for route in app.routes
        if (path := getattr(route, "path", "")).startswith(management_prefixes)
    }
    assert registered
    for path in registered:
        assert any(
            policy.auth_class == "management"
            and path.startswith(policy.path_prefix)
            for policy in ROUTE_POLICIES
        ), path


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/v1/agents", None),
        ("GET", f"/v1/knowledge-bases/status/{uuid4()}", None),
        ("POST", f"/v1/alerts/config/{uuid4()}", None),
        (
            "POST",
            "/v1/extraction-schemas",
            {"tenant_id": str(uuid4()), "name": "test", "fields": []},
        ),
        ("GET", "/v1/usage", None),
        ("GET", "/v1/audit", None),
        (
            "POST",
            "/v1/secrets/rotate",
            {"tenant_id": str(uuid4()), "provider_id": "groq", "new_secret": "x"},
        ),
    ],
)
def test_management_routes_reject_unauthenticated_requests(
    client: TestClient,
    method: str,
    path: str,
    body: dict | None,
) -> None:
    response = client.request(method, path, json=body)
    assert response.status_code == 401, (path, response.text)


def test_agent_routes_derive_tenant_from_api_key(client: TestClient) -> None:
    tenant_id = str(uuid4())
    raw = _key(
        client,
        tenant_id,
        scopes=["agent:read", "agent:write"],
        role="tenant_editor",
    )
    headers = {"Authorization": f"Bearer {raw}"}

    created = client.post("/v1/agents", headers=headers, json={"name": "Agent"})
    assert created.status_code == 201
    assert created.json()["tenant_id"] == tenant_id
    listed = client.get("/v1/agents", headers=headers)
    assert listed.status_code == 200
    assert [item["agent_id"] for item in listed.json()] == [created.json()["agent_id"]]


def test_tenant_header_spoofing_is_rejected(client: TestClient) -> None:
    tenant_id = str(uuid4())
    raw = _key(
        client,
        tenant_id,
        scopes=["agent:read"],
        role="tenant_viewer",
    )
    response = client.get(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {raw}",
            "X-Tenant-Id": str(uuid4()),
        },
    )
    assert response.status_code == 403


def test_api_key_requires_scope_and_role(client: TestClient) -> None:
    tenant_id = str(uuid4())
    missing_scope = _key(
        client,
        tenant_id,
        scopes=["agent:read"],
        role="tenant_editor",
    )
    assert (
        client.post(
            "/v1/agents",
            headers={"Authorization": f"Bearer {missing_scope}"},
            json={"name": "Denied"},
        ).status_code
        == 403
    )

    wrong_role = _key(
        client,
        tenant_id,
        scopes=["agent:write"],
        role="tenant_viewer",
    )
    assert (
        client.post(
            "/v1/agents",
            headers={"Authorization": f"Bearer {wrong_role}"},
            json={"name": "Denied"},
        ).status_code
        == 403
    )


def test_path_and_body_tenant_must_match_context(client: TestClient) -> None:
    tenant_id = str(uuid4())
    other_tenant = str(uuid4())
    raw = _key(
        client,
        tenant_id,
        scopes=["knowledge:read", "alert:write", "extraction:write"],
        role="tenant_admin",
    )
    headers = {"Authorization": f"Bearer {raw}"}

    assert (
        client.get(
            f"/v1/knowledge-bases/status/{other_tenant}", headers=headers
        ).status_code
        == 403
    )
    assert (
        client.post(f"/v1/alerts/config/{other_tenant}", headers=headers).status_code
        == 403
    )
    assert (
        client.post(
            "/v1/extraction-schemas",
            headers=headers,
            json={"tenant_id": other_tenant, "name": "bad", "fields": []},
        ).status_code
        == 403
    )


def test_identity_headers_cannot_raise_role(client: TestClient) -> None:
    tenant_id = str(uuid4())
    raw = _key(
        client,
        tenant_id,
        scopes=["agent:read"],
        role="tenant_viewer",
    )
    response = client.get(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {raw}",
            "X-Actor-Role": "platform_admin",
        },
    )
    assert response.status_code == 403


def test_injected_oidc_identity_uses_same_tenant_boundary(client: TestClient) -> None:
    from control_plane.app import app

    tenant_id = str(uuid4())

    class TestOIDCProvider:
        def authenticate_token(self, token: str) -> dict[str, object]:
            assert token == "signed-dashboard-token"
            return {
                "sub": "dashboard-user",
                "tenant_id": tenant_id,
                "roles": ["tenant_viewer"],
                "scopes": [],
            }

    app.state.oidc_provider = TestOIDCProvider()
    response = client.get(
        "/v1/agents",
        headers={"Authorization": "Bearer signed-dashboard-token"},
    )
    assert response.status_code == 200

    spoofed = client.get(
        "/v1/agents",
        headers={
            "Authorization": "Bearer signed-dashboard-token",
            "X-Tenant-Id": str(uuid4()),
        },
    )
    assert spoofed.status_code == 403
