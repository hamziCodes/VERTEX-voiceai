from __future__ import annotations

from control_plane.auth.jwt import verify_session_jwt
from tests.studio.test_agent_builder_api import _create_agent
from tests.studio.test_identity_api import _create_workspace, _headers


def test_workos_member_mints_tenant_bound_ephemeral_session(studio_api) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)
    created = _create_agent(client, tenant_id)
    published = client.post(
        f"/v1/agents/{created['agent_id']}/publish",
        headers=_headers("owner-token", tenant_id),
        json={"expected_revision": created["draft_revision"]},
    )
    assert published.status_code == 200

    response = client.post(
        "/v1/studio/sessions",
        headers=_headers("owner-token", tenant_id),
        json={"agent_id": created["agent_id"], "test_mode": "mock"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["token"]
    assert payload["ttl_sec"] == 120
    assert payload["ws_url"].startswith("ws")
    claims = verify_session_jwt(payload["token"])
    assert claims["provider_mode_constraint"] == "mock"
    assert claims["stt_transcript_mode_constraint"] == "fixed_mock"


def test_studio_session_mint_requires_identity_and_workspace(studio_api) -> None:
    client, _ = studio_api
    unauthenticated = client.post(
        "/v1/studio/sessions", json={"agent_id": "agent-a"}
    )
    assert unauthenticated.status_code == 401
    response = client.post(
        "/v1/studio/sessions",
        headers={"Authorization": "Bearer owner-token"},
        json={"agent_id": "agent-a"},
    )
    assert response.status_code == 400
