from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from control_plane.studio.models import (
    IdentityContext,
    StudioRole,
    UserIdentity,
    WorkspaceMembership,
)
from control_plane.studio.repository import MembershipNotFoundError


class _ClaimsProvider:
    def __init__(self, claims: dict[str, object]) -> None:
        self.claims = claims

    def authenticate_token(self, token: str) -> dict[str, object]:
        assert token == "verified-oidc-token"
        return dict(self.claims)


@dataclass
class _IdentityRepository:
    identity: UserIdentity
    memberships: tuple[WorkspaceMembership, ...]

    async def resolve_identity(self, identity: IdentityContext) -> UserIdentity:
        if (
            identity.issuer != self.identity.issuer
            or identity.subject != self.identity.subject
        ):
            raise MembershipNotFoundError("Unknown external identity.")
        return self.identity

    async def list_memberships(self, user_id: UUID) -> tuple[WorkspaceMembership, ...]:
        if user_id != self.identity.user_id:
            return ()
        return self.memberships


@pytest.fixture
def studio_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    with TestClient(app) as client:
        yield client, app
    for name in ("oidc_provider", "studio_repository"):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _install_identity(
    app,
    *,
    tenant_id: UUID | None,
    role: StudioRole = "tenant_viewer",
    platform_admin: bool = False,
    claim_overrides: dict[str, object] | None = None,
) -> UserIdentity:
    user = UserIdentity(
        user_id=uuid4(),
        issuer="https://identity.test",
        subject="dashboard-user",
        email="user@example.com",
        is_platform_admin=platform_admin,
    )
    memberships = ()
    if tenant_id is not None:
        memberships = (
            WorkspaceMembership(
                user_id=user.user_id,
                tenant_id=tenant_id,
                tenant_name="Authorized Workspace",
                role=role,
                created_at=datetime.now(UTC),
            ),
        )
    claims: dict[str, object] = {
        "sub": user.subject,
        "iss": user.issuer,
        "email": user.email or "",
    }
    claims.update(claim_overrides or {})
    app.state.oidc_provider = _ClaimsProvider(claims)
    app.state.studio_repository = _IdentityRepository(user, memberships)
    return user


def _headers(tenant_id: UUID, **extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer verified-oidc-token",
        "X-Tenant-Id": str(tenant_id),
        **extra,
    }


def test_oidc_valid_membership_uses_durable_tenant_and_role(studio_client) -> None:
    client, app = studio_client
    tenant_id = uuid4()
    _install_identity(app, tenant_id=tenant_id, role="tenant_viewer")

    response = client.get("/v1/agents", headers=_headers(tenant_id))

    assert response.status_code == 200


def test_oidc_unknown_subject_claim_is_rejected(studio_client) -> None:
    client, app = studio_client
    tenant_id = uuid4()
    _install_identity(app, tenant_id=tenant_id)
    app.state.oidc_provider = _ClaimsProvider(
        {"iss": "https://identity.test", "email": "user@example.com"}
    )

    response = client.get("/v1/agents", headers=_headers(tenant_id))

    assert response.status_code == 401


def test_oidc_unowned_tenant_is_rejected(studio_client) -> None:
    client, app = studio_client
    owned_tenant = uuid4()
    _install_identity(app, tenant_id=owned_tenant)

    response = client.get("/v1/agents", headers=_headers(uuid4()))

    assert response.status_code == 403


def test_oidc_tampered_actor_role_is_rejected(studio_client) -> None:
    client, app = studio_client
    tenant_id = uuid4()
    _install_identity(app, tenant_id=tenant_id, role="tenant_viewer")

    response = client.get(
        "/v1/agents",
        headers=_headers(tenant_id, **{"X-Actor-Role": "platform_admin"}),
    )

    assert response.status_code == 403


def test_oidc_tenant_role_and_scope_claims_never_grant_access(studio_client) -> None:
    client, app = studio_client
    tenant_id = uuid4()
    _install_identity(
        app,
        tenant_id=tenant_id,
        role="tenant_viewer",
        claim_overrides={
            "tenant_id": str(uuid4()),
            "roles": ["platform_admin"],
            "scopes": ["*"],
        },
    )

    read = client.get("/v1/agents", headers=_headers(tenant_id))
    write = client.post(
        "/v1/agents",
        headers=_headers(tenant_id),
        json={"name": "Must not be created"},
    )

    assert read.status_code == 200
    assert write.status_code == 403


def test_oidc_developer_can_read_and_test_but_cannot_edit_agents(studio_client) -> None:
    client, app = studio_client
    tenant_id = uuid4()
    _install_identity(app, tenant_id=tenant_id, role="tenant_developer")

    read = client.get("/v1/agents", headers=_headers(tenant_id))
    mint = client.post(
        "/v1/sessions/mint",
        headers=_headers(tenant_id),
        json={"agent_id": str(uuid4())},
    )
    write = client.post(
        "/v1/agents",
        headers=_headers(tenant_id),
        json={"name": "Must not be created"},
    )

    assert read.status_code == 200
    assert mint.status_code != 403
    assert write.status_code == 403


def test_durable_platform_admin_requires_explicit_tenant(studio_client) -> None:
    client, app = studio_client
    selected_tenant = uuid4()
    _install_identity(
        app,
        tenant_id=None,
        platform_admin=True,
        claim_overrides={"roles": ["tenant_viewer"]},
    )

    missing = client.get(
        "/v1/agents",
        headers={"Authorization": "Bearer verified-oidc-token"},
    )
    explicit = client.get("/v1/agents", headers=_headers(selected_tenant))

    assert missing.status_code == 400
    assert explicit.status_code == 200


def test_api_key_authentication_remains_compatible(studio_client) -> None:
    client, app = studio_client
    tenant_id = str(uuid4())
    raw, _ = app.state.api_keys.generate_api_key(
        tenant_id,
        "studio-compatibility",
        scopes=["agent:read"],
        role="tenant_viewer",
        subject_id="studio-api-key",
    )

    response = client.get(
        "/v1/agents",
        headers={"Authorization": f"Bearer {raw}"},
    )

    assert response.status_code == 200


def test_oidc_stub_refuses_protected_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from control_plane.auth.oidc_hook import OIDCNotConfigured, OIDCProviderStub

    monkeypatch.setenv("UCVE_ENV", "production")

    with pytest.raises(OIDCNotConfigured):
        OIDCProviderStub().authenticate_token("not-a-real-token")
