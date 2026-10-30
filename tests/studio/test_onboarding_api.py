from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from tests.studio.test_identity_api import _create_workspace, _headers


def test_onboarding_can_resume_and_reports_deterministic_requirements(
    studio_api,
) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)

    initial = client.get("/v1/onboarding", headers=_headers("owner-token", tenant_id))
    saved = client.patch(
        "/v1/onboarding",
        headers=_headers("owner-token", tenant_id),
        json={
            "business_name": "Acme Ltd",
            "languages": ["en", "ur", "en"],
            "completed_steps": ["business", "languages"],
        },
    )
    resumed = client.get("/v1/onboarding", headers=_headers("owner-token", tenant_id))

    assert initial.status_code == 200
    assert initial.json()["requirement_codes"] == [
        "business_name_required",
        "use_case_required",
        "operating_region_required",
    ]
    assert saved.status_code == 200
    assert saved.json()["profile"]["languages"] == ["en", "ur"]
    assert resumed.json() == saved.json()


def test_entitlements_are_read_only_and_tenant_bound(studio_api) -> None:
    client: TestClient
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)

    response = client.get(
        "/v1/entitlements", headers=_headers("owner-token", tenant_id)
    )
    missing_tenant = client.get("/v1/entitlements", headers=_headers("owner-token"))
    spoofed = client.get(
        "/v1/entitlements", headers=_headers("owner-token", UUID(int=1))
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == str(tenant_id)
    assert response.json()["telephony_enabled"] is False
    assert missing_tenant.status_code == 400
    assert spoofed.status_code == 403
