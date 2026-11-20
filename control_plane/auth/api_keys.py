"""Tenant API-key lifecycle with hash-at-rest storage."""

from __future__ import annotations

import hashlib
import secrets
import threading
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol

from control_plane.auth.rbac import RBACManager

API_KEY_PREFIX = "ucve_live_"
_AUTH_FAILURE = "Invalid or unauthorized API key."


class APIKeyStore(Protocol):
    durable: bool

    def put(self, key_hash: str, record: dict[str, Any]) -> None: ...
    def get(self, key_hash: str) -> dict[str, Any] | None: ...
    def update(self, key_hash: str, record: dict[str, Any]) -> None: ...
    def find_by_id(self, key_id: str) -> tuple[str, dict[str, Any]] | None: ...
    def list_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]: ...


class InMemoryAPIKeyStore:
    """Thread-safe development/test store. Production must inject a durable store."""

    durable = False

    def __init__(self) -> None:
        self._keys: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def put(self, key_hash: str, record: dict[str, Any]) -> None:
        with self._lock:
            self._keys[key_hash] = deepcopy(record)

    def get(self, key_hash: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._keys.get(key_hash)
            return deepcopy(record) if record else None

    def update(self, key_hash: str, record: dict[str, Any]) -> None:
        self.put(key_hash, record)

    def find_by_id(self, key_id: str) -> tuple[str, dict[str, Any]] | None:
        with self._lock:
            for key_hash, record in self._keys.items():
                if record["key_id"] == key_id:
                    return key_hash, deepcopy(record)
        return None

    def list_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(value)
                for value in self._keys.values()
                if value["tenant_id"] == tenant_id
            ]


class APIKeyManager:
    """Generate, verify, list, and revoke scoped tenant API keys."""

    def __init__(self, store: APIKeyStore | None = None) -> None:
        self._store: APIKeyStore = store or InMemoryAPIKeyStore()

    def assert_runtime_ready(self, environment: str) -> None:
        if (
            environment.lower() in {"production", "prod", "staging"}
            and not self._store.durable
        ):
            raise RuntimeError(
                "Production API-key authentication requires a durable store."
            )

    def generate_api_key(
        self,
        tenant_id: str,
        name: str,
        scopes: list[str] | None = None,
        *,
        role: str = "tenant_viewer",
        subject_id: str | None = None,
        expires_at: datetime | None = None,
        created_by: str | None = None,
        now: datetime | None = None,
    ) -> tuple[str, str]:
        tenant_id = tenant_id.strip()
        name = name.strip()
        role = role.strip().lower()
        if not tenant_id or not name:
            raise ValueError("tenant_id and name are required.")
        if role not in RBACManager.roles():
            raise ValueError("Unknown API-key role.")
        timestamp = now or datetime.now(UTC)
        if expires_at is not None and expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware.")
        key_id = str(uuid.uuid4())
        raw_secret = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        record = {
            "key_id": key_id,
            "subject_id": subject_id or f"api-key:{key_id}",
            "tenant_id": tenant_id,
            "name": name,
            "key_prefix": raw_secret[:16],
            "scopes": sorted(set(scopes or ["session:mint"])),
            "role": role,
            "created_at": timestamp,
            "created_by": created_by,
            "expires_at": expires_at,
            "revoked_at": None,
            "last_used_at": None,
        }
        self._store.put(key_hash, record)
        return raw_secret, key_id

    def verify_api_key(
        self,
        raw_secret: str,
        required_scope: str | None = None,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not raw_secret.startswith(API_KEY_PREFIX):
            raise PermissionError(_AUTH_FAILURE)
        key_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        record = self._store.get(key_hash)
        timestamp = now or datetime.now(UTC)
        if not record or record.get("revoked_at") is not None:
            raise PermissionError(_AUTH_FAILURE)
        expires_at = record.get("expires_at")
        if expires_at is not None and expires_at <= timestamp:
            raise PermissionError(_AUTH_FAILURE)
        scopes = set(record.get("scopes", ()))
        if required_scope and required_scope not in scopes and "*" not in scopes:
            raise PermissionError(_AUTH_FAILURE)
        record["last_used_at"] = timestamp
        self._store.update(key_hash, record)
        return deepcopy(record)

    def revoke_api_key(
        self, tenant_id: str, key_id: str, *, now: datetime | None = None
    ) -> None:
        found = self._store.find_by_id(key_id)
        if not found or found[1]["tenant_id"] != tenant_id:
            raise KeyError("API key not found.")
        key_hash, record = found
        record["revoked_at"] = now or datetime.now(UTC)
        self._store.update(key_hash, record)

    def list_api_keys(self, tenant_id: str) -> list[dict[str, Any]]:
        return sorted(
            self._store.list_for_tenant(tenant_id),
            key=lambda item: item["created_at"],
        )
