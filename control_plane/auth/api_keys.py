"""UCVE API Key Manager."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Any


class APIKeyManager:
    """Manager for generating, hashing, and verifying tenant API keys."""

    def __init__(self) -> None:
        self._keys_db: dict[str, dict[str, Any]] = {}

    def generate_api_key(
        self, tenant_id: str, name: str, scopes: list[str] | None = None
    ) -> tuple[str, str]:
        """Generate new tenant API key, returning (raw_secret_key, key_id)."""
        key_id = str(uuid.uuid4())
        prefix = "ucve_live_"
        raw_secret = f"{prefix}{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

        self._keys_db[key_hash] = {
            "key_id": key_id,
            "tenant_id": tenant_id,
            "name": name,
            "scopes": scopes or ["session:mint"],
            "revoked": False,
        }
        return raw_secret, key_id

    def verify_api_key(
        self, raw_secret: str, required_scope: str | None = None
    ) -> dict[str, Any]:
        """Verify API key secret and return record if valid and authorized."""
        key_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        record = self._keys_db.get(key_hash)

        if not record or record.get("revoked", False):
            raise PermissionError("Invalid or revoked API key.")

        if required_scope and required_scope not in record.get("scopes", []):
            raise PermissionError(f"API key missing required scope '{required_scope}'.")

        return record
