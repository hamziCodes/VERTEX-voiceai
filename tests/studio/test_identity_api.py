from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient


def _headers(token: str, tenant_id: UUID | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if tenant_id is not None:
        headers["X-Tenant-Id"] = str(tenant_id)
    return headers


def _create_workspace(client: TestClient) -> tuple[UUID, UUID]:
    response = client.post(
        "/v1/organizations",
        headers=_headers("owner-token"),
        json={"name": "Acme Support"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return UUID(payload["tenant_id"]), UUID(payload["user_id"])


def test_first_workspace_creation_and_me_are_identity_scoped(studio_api) -> None:
    client, _ = studio_api

    before = client.get("/v1/me", headers=_headers("owner-token"))
    tenant_id, owner_id = _create_workspace(client)
    after = client.get("/v1/me", headers=_headers("owner-token"))

    assert before.status_code == 200
    assert before.json()["memberships"] == []
    assert after.status_code == 200
    assert after.json()["user_id"] == str(owner_id)
    assert after.json()["memberships"] == [
        {
            "user_id": str(owner_id),
            "tenant_id": str(tenant_id),
            "tenant_name": "Acme Support",
            "role": "tenant_admin",
            "created_at": after.json()["memberships"][0]["created_at"],
        }
    ]


def test_invitation_acceptance_is_single_use_and_members_are_listed(studio_api) -> None:
    client, _ = studio_api
    tenant_id, owner_id = _create_workspace(client)
    created = client.post(
        f"/v1/organizations/{tenant_id}/invitations",
        headers=_headers("owner-token", tenant_id),
        json={"email": "member@example.com", "role": "tenant_editor"},
    )

    assert created.status_code == 201, created.text
    token = created.json()["token"]
    assert token
    accepted = client.post(
        "/v1/invitations/accept",
        headers=_headers("member-token"),
        json={"token": token},
    )
    replay = client.post(
        "/v1/invitations/accept",
        headers=_headers("member-token"),
        json={"token": token},
    )
    members = client.get(
        f"/v1/organizations/{tenant_id}/members",
        headers=_headers("owner-token", tenant_id),
    )

    assert accepted.status_code == 200
    assert replay.status_code == 409
    assert members.status_code == 200
    assert {(item["user_id"], item["role"]) for item in members.json()} == {
        (str(owner_id), "tenant_admin"),
        (accepted.json()["user_id"], "tenant_editor"),
    }
    assert "token" not in members.text


def test_expired_invitation_is_rejected(studio_api) -> None:
    client, app = studio_api
    tenant_id, owner_id = _create_workspace(client)
    raw_token = "expired-invitation-token"
    awaitable = app.state.studio_repository.create_invitation(
        tenant_id,
        email="member@example.com",
        role="tenant_viewer",
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        invited_by=owner_id,
    )
    import asyncio

    asyncio.run(awaitable)

    response = client.post(
        "/v1/invitations/accept",
        headers=_headers("member-token"),
        json={"token": raw_token},
    )

    assert response.status_code == 410


def test_member_role_change_and_last_admin_protection(studio_api) -> None:
    client, _ = studio_api
    tenant_id, owner_id = _create_workspace(client)

    protected = client.patch(
        f"/v1/organizations/{tenant_id}/members/{owner_id}",
        headers=_headers("owner-token", tenant_id),
        json={"role": "tenant_viewer"},
    )
    removal = client.delete(
        f"/v1/organizations/{tenant_id}/members/{owner_id}",
        headers=_headers("owner-token", tenant_id),
    )

    assert protected.status_code == 409
    assert removal.status_code == 409


def test_workspace_routes_reject_tenant_mismatch(studio_api) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)

    response = client.get(
        f"/v1/organizations/{tenant_id}/members",
        headers=_headers("owner-token", UUID(int=1)),
    )

    assert response.status_code == 403
