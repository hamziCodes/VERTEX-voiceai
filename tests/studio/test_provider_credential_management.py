from __future__ import annotations

from core.secrets.kms.local_dev import LocalDevKMSBackend
from core.secrets.repository import InMemorySecretRepository
from core.secrets.vault import SecretVault
from tests.studio.test_identity_api import _create_workspace, _headers


def test_provider_credential_lifecycle_redacts_value_and_invalidates_cache(
    studio_api,
) -> None:
    client, app = studio_api
    tenant_id, _ = _create_workspace(client)
    vault = SecretVault(
        kms_backend=LocalDevKMSBackend(master_key="phase13-task6-test-key"),
        repository=InMemorySecretRepository(),
    )
    app.state.secret_vault = vault
    secret_value = "task6-super-sensitive-provider-value"
    created = client.post(
        "/v1/provider-credentials",
        headers=_headers("owner-token", tenant_id),
        json={
            "provider_id": "groq",
            "credential_type": "api_key",
            "reference": "primary",
            "secret": secret_value,
        },
    )

    assert created.status_code == 201, created.text
    credential_id = created.json()["credential_id"]
    listed = client.get(
        "/v1/provider-credentials", headers=_headers("owner-token", tenant_id)
    )
    vault.resolve_credential(
        str(tenant_id), "groq", credential_ref="primary", tier="byok"
    )
    assert len(vault.cache) == 1
    revoked = client.delete(
        f"/v1/provider-credentials/{credential_id}",
        headers=_headers("owner-token", tenant_id),
    )

    assert secret_value not in created.text
    assert secret_value not in listed.text
    assert "encrypted_blob" not in created.text + listed.text
    assert listed.json()["credentials"][0]["status"] == "active"
    assert revoked.status_code == 204
    assert len(vault.cache) == 0


def test_provider_credential_response_has_only_safe_metadata(studio_api) -> None:
    client, app = studio_api
    tenant_id, _ = _create_workspace(client)
    app.state.secret_vault = SecretVault(
        kms_backend=LocalDevKMSBackend(master_key="phase13-redaction-test-key"),
        repository=InMemorySecretRepository(),
    )
    response = client.post(
        "/v1/provider-credentials",
        headers=_headers("owner-token", tenant_id),
        json={
            "provider_id": "cartesia",
            "reference": "voice",
            "secret": "never-return-this-value",
        },
    )

    assert response.status_code == 201
    assert set(response.json()) == {
        "credential_id",
        "provider_id",
        "credential_type",
        "reference",
        "rotation_version",
        "status",
        "created_at",
        "rotated_at",
    }
    serialized = repr(response.json())
    for forbidden in ("never-return-this-value", "encrypted_blob", "key_version"):
        assert forbidden not in serialized
