"""UCVE Control-Plane Admin Secret Rotation Route Handlers."""

from __future__ import annotations

from typing import Any

from core.secrets.vault import SecretVault, build_secret_vault

_vault_instance: SecretVault | None = None


def get_secret_vault() -> SecretVault:
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = build_secret_vault()
    return _vault_instance


async def handle_rotate_secret(
    tenant_id: str, provider_id: str, new_secret: str
) -> tuple[int, dict[str, Any]]:
    """Admin route handler for tenant credential rotation."""
    if not tenant_id or not provider_id or not new_secret:
        return 400, {"error": "tenant_id, provider_id, and new_secret are required."}

    await get_secret_vault().arotate(tenant_id, provider_id, new_secret)
    return 200, {
        "status": "success",
        "tenant_id": tenant_id,
        "provider_id": provider_id,
        "message": "Credential rotated and cache invalidated successfully.",
    }
