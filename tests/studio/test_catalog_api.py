from __future__ import annotations

from tests.studio.test_identity_api import _create_workspace, _headers


def test_provider_catalog_filters_capabilities_without_internal_fields(
    studio_api,
) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)

    response = client.get(
        "/v1/catalog/providers?category=tts&language=ur",
        headers=_headers("owner-token", tenant_id),
    )

    assert response.status_code == 200
    providers = response.json()["providers"]
    assert [item["provider_id"] for item in providers] == ["cartesia", "uplift"]
    assert all(item["category"] == "tts" for item in providers)
    assert "credential_policy" not in response.text
    assert "credentials_ref" not in response.text


def test_templates_are_source_controlled_and_reference_known_providers(
    studio_api,
) -> None:
    client, _ = studio_api
    tenant_id, _ = _create_workspace(client)

    response = client.get(
        "/v1/agents/templates", headers=_headers("owner-token", tenant_id)
    )

    assert response.status_code == 200
    assert [item["template_id"] for item in response.json()["templates"]] == [
        "clinic_intake",
        "retail_customer_service",
    ]
    provider_ids = {
        route["provider_id"]
        for template in response.json()["templates"]
        for category in template["config"]["providers"].values()
        for group in category
        for route in group["routes"]
    }
    assert "whisper" not in provider_ids
