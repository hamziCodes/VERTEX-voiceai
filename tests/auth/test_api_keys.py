from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from control_plane.auth.api_keys import APIKeyManager, InMemoryAPIKeyStore


def test_api_key_lifecycle_tracks_safe_metadata() -> None:
    store = InMemoryAPIKeyStore()
    manager = APIKeyManager(store)
    now = datetime(2026, 10, 22, tzinfo=UTC)
    raw_key, key_id = manager.generate_api_key(
        "tenant-a",
        "server",
        scopes=["agent:read"],
        role="tenant_viewer",
        subject_id="service-a",
        expires_at=now + timedelta(hours=1),
        now=now,
    )

    record = manager.verify_api_key(
        raw_key,
        required_scope="agent:read",
        now=now + timedelta(minutes=1),
    )

    assert record["key_id"] == key_id
    assert record["tenant_id"] == "tenant-a"
    assert record["subject_id"] == "service-a"
    assert record["last_used_at"] == now + timedelta(minutes=1)
    metadata = manager.list_api_keys("tenant-a")
    assert metadata[0]["key_id"] == key_id
    assert "key_hash" not in metadata[0]
    assert raw_key not in repr(metadata)


def test_expired_and_revoked_keys_fail_closed() -> None:
    manager = APIKeyManager()
    now = datetime(2026, 10, 22, tzinfo=UTC)
    expired, _ = manager.generate_api_key(
        "tenant-a",
        "expired",
        expires_at=now - timedelta(seconds=1),
        now=now - timedelta(hours=1),
    )
    with pytest.raises(PermissionError, match="Invalid or unauthorized"):
        manager.verify_api_key(expired, now=now)

    active, key_id = manager.generate_api_key("tenant-a", "active", now=now)
    manager.revoke_api_key("tenant-a", key_id, now=now)
    with pytest.raises(PermissionError, match="Invalid or unauthorized"):
        manager.verify_api_key(active, now=now)


def test_scope_role_and_tenant_inputs_are_validated() -> None:
    manager = APIKeyManager()
    with pytest.raises(ValueError):
        manager.generate_api_key("", "name")
    with pytest.raises(ValueError):
        manager.generate_api_key("tenant", "", role="tenant_viewer")
    with pytest.raises(ValueError):
        manager.generate_api_key("tenant", "name", role="unknown")

    raw, _ = manager.generate_api_key("tenant-a", "read-only", scopes=["agent:read"])
    with pytest.raises(PermissionError, match="Invalid or unauthorized"):
        manager.verify_api_key(raw, required_scope="agent:write")


def test_production_requires_durable_api_key_store() -> None:
    with pytest.raises(RuntimeError, match="durable"):
        APIKeyManager().assert_runtime_ready(environment="production")
