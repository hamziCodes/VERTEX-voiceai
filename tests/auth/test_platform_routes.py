"""Phase 13J: platform staff authorization dependency and internal API."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from control_plane.studio.repository import InMemoryStudioRepository

REASON = "Support rota for Q4 onboarding"
PLATFORM_GETS = (
    "/v1/platform/me",
    "/v1/platform/tenants",
    "/v1/platform/staff",
    "/v1/platform/audit",
)


class _Claims:
    def authenticate_token(self, token: str) -> dict[str, object]:
        name = token.removesuffix("-token")
        if name == token:
            raise KeyError(token)
        return {
            "sub": name,
            "iss": "https://identity.test",
            "email": f"{name}@wavia.test",
        }


def _auth(name: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {name}-token", **extra}


@pytest.fixture
def platform_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    repository = InMemoryStudioRepository()
    with TestClient(app) as client:
        app.state.oidc_provider = _Claims()
        app.state.studio_repository = repository
        ids: dict[str, UUID] = {}
        for name in ("admin", "support", "customer", "second"):
            response = client.get("/v1/me", headers=_auth(name))
            assert response.status_code == 200, response.text
            ids[name] = UUID(response.json()["user_id"])
        asyncio.run(
            repository.bootstrap_platform_admin(
                ids["admin"], reason="Initial operator bootstrap"
            )
        )
        granted = client.put(
            "/v1/platform/staff",
            headers=_auth("admin"),
            json={
                "email": "support@wavia.test",
                "role": "platform_support",
                "reason": REASON,
            },
        )
        assert granted.status_code == 200, granted.text
        tenant = client.post(
            "/v1/organizations", headers=_auth("customer"), json={"name": "Acme"}
        )
        assert tenant.status_code == 201
        ids["tenant"] = UUID(tenant.json()["tenant_id"])
        yield client, repository, ids
    for name in ("oidc_provider", "studio_repository"):
        if hasattr(app.state, name):
            delattr(app.state, name)


@pytest.mark.parametrize("path", PLATFORM_GETS)
def test_platform_routes_require_oidc(platform_api, path: str) -> None:
    client, _, _ = platform_api
    assert client.get(path).status_code == 401
    invalid = {"Authorization": "Bearer unverifiable"}
    assert client.get(path, headers=invalid).status_code == 401
    api_key = {"Authorization": "Bearer ucve_live_not-a-staff-credential"}
    assert client.get(path, headers=api_key).status_code == 401


@pytest.mark.parametrize("path", PLATFORM_GETS)
def test_platform_routes_reject_tenant_and_role_context(platform_api, path) -> None:
    client, _, ids = platform_api
    with_tenant = _auth("admin", **{"X-Tenant-Id": str(ids["tenant"])})
    with_role = _auth("admin", **{"X-Actor-Role": "platform_admin"})
    assert client.get(path, headers=with_tenant).status_code == 400
    assert client.get(path, headers=with_role).status_code == 400


@pytest.mark.parametrize("path", PLATFORM_GETS)
def test_customers_are_denied_every_platform_route(platform_api, path) -> None:
    client, _, _ = platform_api
    assert client.get(path, headers=_auth("customer")).status_code == 403


def test_platform_me_reports_role_and_capabilities(platform_api) -> None:
    client, _, ids = platform_api
    admin = client.get("/v1/platform/me", headers=_auth("admin")).json()
    support = client.get("/v1/platform/me", headers=_auth("support")).json()
    assert admin == {
        "user_id": str(ids["admin"]),
        "email": "admin@wavia.test",
        "role": "platform_admin",
        "capabilities": [
            "platform_alerts:manage",
            "platform_alerts:read",
            "platform_audit:read",
            "platform_operations:read",
            "platform_staff:read",
            "platform_staff:write",
            "platform_support_session:manage",
            "platform_support_session:read",
            "platform_support_session:write",
            "platform_tenant:read",
        ],
    }
    assert support["role"] == "platform_support"
    assert support["capabilities"] == [
        "platform_support_session:read",
        "platform_support_session:write",
        "platform_tenant:read",
    ]


def test_identity_reports_durable_platform_role(platform_api) -> None:
    client, _, _ = platform_api
    admin = client.get("/v1/me", headers=_auth("admin")).json()
    support = client.get("/v1/me", headers=_auth("support")).json()
    customer = client.get("/v1/me", headers=_auth("customer")).json()
    assert admin["platform_role"] == "platform_admin"
    assert admin["is_platform_admin"] is True
    assert support["platform_role"] == "platform_support"
    assert support["is_platform_admin"] is False
    assert support["platform_capabilities"] == [
        "platform_support_session:read",
        "platform_support_session:write",
        "platform_tenant:read",
    ]
    assert customer["platform_role"] is None
    assert customer["platform_capabilities"] == []
    assert customer["is_platform_admin"] is False


def test_support_reads_tenants_but_not_staff_or_audit(platform_api) -> None:
    client, _, ids = platform_api
    directory = client.get(
        "/v1/platform/tenants", params={"q": "acme"}, headers=_auth("support")
    )
    assert directory.status_code == 200
    body = directory.json()
    assert body["total"] == 1
    assert body["items"][0]["tenant_id"] == str(ids["tenant"])
    detail = client.get(
        f"/v1/platform/tenants/{ids['tenant']}", headers=_auth("support")
    )
    assert detail.status_code == 200
    assert detail.json()["members_by_role"] == {"tenant_admin": 1}
    assert client.get("/v1/platform/staff", headers=_auth("support")).status_code == 403
    assert client.get("/v1/platform/audit", headers=_auth("support")).status_code == 403
    denied = client.put(
        "/v1/platform/staff",
        headers=_auth("support"),
        json={"email": "second@wavia.test", "role": "platform_admin", "reason": REASON},
    )
    assert denied.status_code == 403


def test_directory_bounds_and_unknown_tenant(platform_api) -> None:
    client, _, _ = platform_api
    for params in ({"limit": 0}, {"limit": 51}, {"offset": -1}, {"offset": 10_001}):
        response = client.get(
            "/v1/platform/tenants", params=params, headers=_auth("admin")
        )
        assert response.status_code == 422
    missing = client.get(f"/v1/platform/tenants/{uuid4()}", headers=_auth("admin"))
    assert missing.status_code == 404


def test_tenant_detail_is_audited_and_safe(platform_api) -> None:
    client, _, ids = platform_api
    detail = client.get(f"/v1/platform/tenants/{ids['tenant']}", headers=_auth("admin"))
    assert detail.status_code == 200
    text = detail.text
    for forbidden in ("token", "secret", "password", "email", "key_hash"):
        assert forbidden not in text
    audit = client.get("/v1/platform/audit", headers=_auth("admin")).json()
    assert audit[0]["action"] == "platform_tenant.viewed"
    assert audit[0]["target_tenant_id"] == str(ids["tenant"])
    assert audit[0]["actor_user_id"] == str(ids["admin"])


def test_staff_grant_and_revoke_contract(platform_api) -> None:
    client, _, ids = platform_api
    short = client.put(
        "/v1/platform/staff",
        headers=_auth("admin"),
        json={"email": "second@wavia.test", "role": "platform_admin", "reason": "no"},
    )
    assert short.status_code == 422
    unknown_role = client.put(
        "/v1/platform/staff",
        headers=_auth("admin"),
        json={"email": "second@wavia.test", "role": "tenant_admin", "reason": REASON},
    )
    assert unknown_role.status_code == 422
    missing = client.put(
        "/v1/platform/staff",
        headers=_auth("admin"),
        json={
            "email": "ghost@wavia.test",
            "role": "platform_support",
            "reason": REASON,
        },
    )
    assert missing.status_code == 404
    last = client.post(
        f"/v1/platform/staff/{ids['admin']}/revoke",
        headers=_auth("admin"),
        json={"reason": REASON},
    )
    assert last.status_code == 409

    staff = client.get("/v1/platform/staff", headers=_auth("admin"))
    assert staff.status_code == 200
    assert {item["role"] for item in staff.json()} == {
        "platform_admin",
        "platform_support",
    }
    revoked = client.post(
        f"/v1/platform/staff/{ids['support']}/revoke",
        headers=_auth("admin"),
        json={"reason": "Left the support rota"},
    )
    assert revoked.status_code == 204
    assert client.get("/v1/platform/me", headers=_auth("support")).status_code == 403
    again = client.post(
        f"/v1/platform/staff/{ids['support']}/revoke",
        headers=_auth("admin"),
        json={"reason": "Left the support rota"},
    )
    assert again.status_code == 404


def test_platform_role_never_reaches_tenant_routes(platform_api) -> None:
    client, _, ids = platform_api
    response = client.get(
        "/v1/agents", headers=_auth("admin", **{"X-Tenant-Id": str(ids["tenant"])})
    )
    assert response.status_code == 403
