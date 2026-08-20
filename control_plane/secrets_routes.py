"""UCVE Control-Plane Admin Secret Rotation Route Handlers."""

from __future__ import annotations

from typing import Any

from core.secrets.vault import SecretVault

_vault_instance = SecretVault()


def handle_rotate_secret(
    tenant_id: str, provider_id: str, new_secret: str
) -> tuple[int, dict[str, Any]]:
    """Admin route handler for tenant credential rotation."""
    if not tenant_id or not provider_id or not new_secret:
        return 400, {"error": "tenant_id, provider_id, and new_secret are required."}

    _vault_instance.rotate(tenant_id, provider_id, new_secret)
    return 200, {
        "status": "success",
        "tenant_id": tenant_id,
        "provider_id": provider_id,
        "message": "Credential rotated and cache invalidated successfully.",
    }
