from __future__ import annotations

import asyncio
from inspect import isawaitable

import pytest

from tests.studio.test_identity_api import _create_workspace, _headers


def _resolve(value):  # type: ignore[no-untyped-def]
    return asyncio.run(value) if isawaitable(value) else value


def test_api_key_plaintext_is_returned_once_then_revoked(studio_api) -> None:
    client, app = studio_api
    tenant_id, _ = _create_workspace(client)
    created = client.post(
        "/v1/api-keys",
        headers=_headers("owner-token", tenant_id),
        json={
            "name": "Backend",
            "role": "tenant_viewer",
            "scopes": ["agent:read"],
        },
    )

    assert created.status_code == 201, created.text
    plaintext = created.json()["api_key"]
    key_id = created.json()["key"]["key_id"]
    listed = client.get("/v1/api-keys", headers=_headers("owner-token", tenant_id))
    revoked = client.delete(
        f"/v1/api-keys/{key_id}", headers=_headers("owner-token", tenant_id)
    )

    assert plaintext.startswith("ucve_live_")
    assert listed.status_code == 200
    assert plaintext not in listed.text
    assert "api_key" not in listed.text
    assert revoked.status_code == 204
    with pytest.raises(PermissionError):
        _resolve(app.state.api_keys.verify_api_key(plaintext))


def test_api_key_quota_and_role_are_enforced(studio_api) -> None:
    client, app = studio_api
    tenant_id, _ = _create_workspace(client)
    for index in range(2):
        response = client.post(
            "/v1/api-keys",
            headers=_headers("owner-token", tenant_id),
            json={"name": f"key-{index}", "scopes": ["agent:read"]},
        )
        assert response.status_code == 201
    quota = client.post(
        "/v1/api-keys",
        headers=_headers("owner-token", tenant_id),
        json={"name": "over-quota", "scopes": ["agent:read"]},
    )
    viewer_secret, _ = app.state.api_keys.generate_api_key(
        str(tenant_id),
        "viewer",
        scopes=["api_key:write"],
        role="tenant_viewer",
    )
    forbidden = client.post(
        "/v1/api-keys",
        headers={"Authorization": f"Bearer {viewer_secret}"},
        json={"name": "forbidden", "scopes": ["agent:read"]},
    )

    assert quota.status_code == 409
    assert forbidden.status_code == 403
