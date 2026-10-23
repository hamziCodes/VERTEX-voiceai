"""Async durable API-key lifecycle backed by tenant-isolated PostgreSQL."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from control_plane.auth.api_keys import _AUTH_FAILURE, API_KEY_PREFIX
from control_plane.auth.rbac import RBACManager
from core.db.async_pg import AsyncDatabase, get_default_database


class AsyncAPIKeyManager:
    durable = True

    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    def assert_runtime_ready(self, environment: str) -> None:
        del environment

    async def generate_api_key(
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
        normalized_scopes = sorted(set(scopes or ["session:mint"]))
        async with self.database.tenant_transaction(tenant_id) as connection:
            await connection.execute(
                """
                INSERT INTO api_keys (
                    id, subject_id, tenant_id, name, key_prefix, key_hash,
                    scopes, role, created_at, created_by, expires_at
                ) VALUES (
                    %s::uuid, %s, %s::uuid, %s, %s, %s,
                    %s::jsonb, %s, %s, %s, %s
                )
                """,
                (
                    key_id,
                    subject_id or f"api-key:{key_id}",
                    tenant_id,
                    name,
                    raw_secret[:16],
                    key_hash,
                    __import__("json").dumps(normalized_scopes),
                    role,
                    timestamp,
                    created_by,
                    expires_at,
                ),
            )
        return raw_secret, key_id

    async def verify_api_key(
        self,
        raw_secret: str,
        required_scope: str | None = None,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not raw_secret.startswith(API_KEY_PREFIX):
            raise PermissionError(_AUTH_FAILURE)
        key_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT key_id, subject_id, tenant_id, name, scopes, role, "
                "created_at, expires_at, revoked_at, last_used_at "
                "FROM authenticate_api_key(%s)",
                (key_hash,),
            )
            row = await cursor.fetchone()
        timestamp = now or datetime.now(UTC)
        if row is None or row[8] is not None:
            raise PermissionError(_AUTH_FAILURE)
        if row[7] is not None and row[7] <= timestamp:
            raise PermissionError(_AUTH_FAILURE)
        scopes = set(row[4] or ())
        if required_scope and required_scope not in scopes and "*" not in scopes:
            raise PermissionError(_AUTH_FAILURE)
        tenant_id = str(row[2])
        async with self.database.tenant_transaction(tenant_id) as connection:
            await connection.execute(
                "UPDATE api_keys SET last_used_at = %s "
                "WHERE tenant_id = %s::uuid AND id = %s::uuid",
                (timestamp, tenant_id, str(row[0])),
            )
        return {
            "key_id": str(row[0]),
            "subject_id": str(row[1]),
            "tenant_id": tenant_id,
            "name": str(row[3]),
            "scopes": sorted(scopes),
            "role": str(row[5]),
            "created_at": row[6],
            "expires_at": row[7],
            "revoked_at": row[8],
            "last_used_at": timestamp,
        }

    async def revoke_api_key(
        self, tenant_id: str, key_id: str, *, now: datetime | None = None
    ) -> None:
        async with self.database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                "UPDATE api_keys SET revoked_at = %s "
                "WHERE tenant_id = %s::uuid AND id = %s::uuid "
                "RETURNING id",
                (now or datetime.now(UTC), tenant_id, key_id),
            )
            if await cursor.fetchone() is None:
                raise KeyError("API key not found.")

    async def list_api_keys(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self.database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                "SELECT id::text, subject_id, name, key_prefix, scopes, role, "
                "created_at, created_by, expires_at, revoked_at, last_used_at "
                "FROM api_keys WHERE tenant_id = %s::uuid ORDER BY created_at",
                (tenant_id,),
            )
            rows = await cursor.fetchall()
        return [
            {
                "key_id": row[0],
                "subject_id": row[1],
                "tenant_id": tenant_id,
                "name": row[2],
                "key_prefix": row[3],
                "scopes": list(row[4] or []),
                "role": row[5],
                "created_at": row[6],
                "created_by": row[7],
                "expires_at": row[8],
                "revoked_at": row[9],
                "last_used_at": row[10],
            }
            for row in rows
        ]


def build_api_key_manager() -> Any:
    from core.db.pg import use_memory_repos

    if use_memory_repos():
        from control_plane.auth.api_keys import APIKeyManager

        return APIKeyManager()
    return AsyncAPIKeyManager()
