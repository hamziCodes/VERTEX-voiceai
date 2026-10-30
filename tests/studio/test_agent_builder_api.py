from __future__ import annotations

from uuid import UUID, uuid4

from control_plane.routes import agents as agent_routes
from tests.studio.test_identity_api import _create_workspace, _headers


def _create_agent(client, tenant_id: UUID) -> dict:
    response = client.post(
        "/v1/agents",
        headers=_headers("owner-token", tenant_id),
        json={"name": "Revision Agent"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_stale_two_editor_autosave_fails_without_mutation(studio_api) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)
    created = _create_agent(client, tenant_id)
    agent_id = created["agent_id"]

    first = client.patch(
        f"/v1/agents/{agent_id}/autosave",
        headers=_headers("owner-token", tenant_id),
        json={
            "patch": {"description": "first editor"},
            "expected_revision": created["draft_revision"],
            "force": True,
        },
    )
    stale = client.patch(
        f"/v1/agents/{agent_id}/autosave",
        headers=_headers("owner-token", tenant_id),
        json={
            "patch": {"description": "stale editor"},
            "expected_revision": created["draft_revision"],
            "force": True,
        },
    )
    current = client.get(
        f"/v1/agents/{agent_id}", headers=_headers("owner-token", tenant_id)
    )

    assert first.status_code == 200
    assert first.json()["agent"]["draft_revision"] == created["draft_revision"] + 1
    assert stale.status_code == 409
    assert current.json()["description"] == "first editor"


def test_validate_publish_and_restore_preserve_immutable_versions(studio_api) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)
    created = _create_agent(client, tenant_id)
    agent_id = created["agent_id"]

    validation = client.post(
        f"/v1/agents/{agent_id}/validate",
        headers=_headers("owner-token", tenant_id),
    )
    published = client.post(
        f"/v1/agents/{agent_id}/publish",
        headers=_headers("owner-token", tenant_id),
        json={"expected_revision": created["draft_revision"]},
    )
    stale_publish = client.post(
        f"/v1/agents/{agent_id}/publish",
        headers=_headers("owner-token", tenant_id),
        json={"expected_revision": created["draft_revision"]},
    )
    revision_after_publish = published.json()["config"]["draft_revision"]
    changed = client.patch(
        f"/v1/agents/{agent_id}/autosave",
        headers=_headers("owner-token", tenant_id),
        json={
            "patch": {"name": "Changed draft"},
            "expected_revision": revision_after_publish,
            "force": True,
        },
    )
    restored = client.post(
        f"/v1/agents/{agent_id}/versions/1/restore",
        headers=_headers("owner-token", tenant_id),
        json={"expected_revision": changed.json()["agent"]["draft_revision"]},
    )
    old_version = client.get(
        f"/v1/agents/{agent_id}/versions/1",
        headers=_headers("owner-token", tenant_id),
    )

    assert validation.status_code == 200
    assert validation.json() == {"is_valid": True, "errors": []}
    assert published.status_code == 200
    assert stale_publish.status_code == 409
    assert restored.status_code == 200
    assert restored.json()["name"] == "Revision Agent"
    assert restored.json()["is_published"] is False
    assert old_version.json()["name"] == "Revision Agent"
    assert old_version.json()["is_published"] is True


def test_active_session_pin_does_not_change_after_restore(studio_api) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)
    created = _create_agent(client, tenant_id)
    agent_id = created["agent_id"]
    published = client.post(
        f"/v1/agents/{agent_id}/publish",
        headers=_headers("owner-token", tenant_id),
        json={"expected_revision": created["draft_revision"]},
    )
    session_id = uuid4()
    pinned = client.post(
        f"/v1/agents/{agent_id}/pin",
        headers=_headers("owner-token", tenant_id),
        json={"session_id": str(session_id), "version": 1},
    )
    restored = client.post(
        f"/v1/agents/{agent_id}/versions/1/restore",
        headers=_headers("owner-token", tenant_id),
        json={"expected_revision": published.json()["config"]["draft_revision"]},
    )

    assert pinned.status_code == 200
    assert restored.status_code == 200
    pinned_config = agent_routes.get_pin_engine().get_pinned_config(session_id)
    assert pinned_config is not None
    assert pinned_config.version == 1
    assert pinned_config.is_published is True


def test_validation_returns_stable_structured_issues(studio_api) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)
    created = _create_agent(client, tenant_id)
    agent_id = created["agent_id"]
    changed = client.patch(
        f"/v1/agents/{agent_id}/autosave",
        headers=_headers("owner-token", tenant_id),
        json={
            "patch": {
                "compliance": {
                    "tier": "hipaa",
                    "hipaa_baa_acknowledged": False,
                }
            },
            "expected_revision": created["draft_revision"],
            "force": True,
        },
    )
    validation = client.post(
        f"/v1/agents/{agent_id}/validate",
        headers=_headers("owner-token", tenant_id),
    )

    assert changed.status_code == 200
    assert validation.status_code == 200
    assert validation.json()["is_valid"] is False
    assert all(
        set(issue) == {"code", "message", "field"}
        for issue in validation.json()["errors"]
    )


def test_agent_creation_enforces_workspace_entitlement(studio_api) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)

    first = client.post(
        "/v1/agents",
        headers=_headers("owner-token", tenant_id),
        json={"name": "First agent"},
    )
    second = client.post(
        "/v1/agents",
        headers=_headers("owner-token", tenant_id),
        json={"name": "Second agent"},
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "Agent limit reached for this workspace."}
