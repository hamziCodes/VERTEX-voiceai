"""UCVE API Key Manager (prefix ucve_live_; hash-at-rest)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Any, Protocol


API_KEY_PREFIX = "ucve_live_"


class APIKeyStore(Protocol):
    """Persistence port for api_keys rows (in-memory now; Postgres in H3)."""

    def put(self, key_hash: str, record: dict[str, Any]) -> None: ...

    def get(self, key_hash: str) -> dict[str, Any] | None: ...


class InMemoryAPIKeyStore:
    def __init__(self) -> None:
        self._keys: dict[str, dict[str, Any]] = {}

    def put(self, key_hash: str, record: dict[str, Any]) -> None:
        self._keys[key_hash] = record

    def get(self, key_hash: str) -> dict[str, Any] | None:
        return self._keys.get(key_hash)


class APIKeyManager:
    """Manager for generating, hashing, and verifying tenant API keys."""

    def __init__(self, store: APIKeyStore | None = None) -> None:
        self._store: APIKeyStore = store or InMemoryAPIKeyStore()

    def generate_api_key(
        self, tenant_id: str, name: str, scopes: list[str] | None = None
    ) -> tuple[str, str]:
        """Generate new tenant API key, returning (raw_secret_key, key_id)."""
        key_id = str(uuid.uuid4())
        raw_secret = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        record = {
            "key_id": key_id,
            "tenant_id": tenant_id,
            "name": name,
            "key_prefix": API_KEY_PREFIX,
            "scopes": scopes or ["session:mint"],
            "role": "tenant_viewer",
            "revoked": False,
        }
        self._store.put(key_hash, record)
        return raw_secret, key_id

    def verify_api_key(
        self, raw_secret: str, required_scope: str | None = None
    ) -> dict[str, Any]:
        """Verify API key secret and return record if valid and authorized."""
        if not raw_secret.startswith(API_KEY_PREFIX):
            raise PermissionError("Invalid or revoked API key.")
        key_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        record = self._store.get(key_hash)

        if not record or record.get("revoked", False):
            raise PermissionError("Invalid or revoked API key.")

        if required_scope and required_scope not in record.get("scopes", []):
            raise PermissionError(f"API key missing required scope '{required_scope}'.")

        return record
