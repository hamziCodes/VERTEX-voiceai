"""Encrypted tenant-secret repository contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from core.db.async_pg import AsyncDatabase, get_default_database


@dataclass(frozen=True, slots=True)
class CredentialRecord:
    """Encrypted credential record safe to persist outside a worker."""

    tenant_id: str
    provider_id: str
    credential_type: str
    credential_ref: str
    encrypted_blob: str
    key_version: int
    rotation_version: int
    created_at: datetime | None = None
    rotated_at: datetime | None = None


class SecretRepository(Protocol):
    """Persistence port for encrypted tenant credentials."""

    def get(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str,
        credential_ref: str,
    ) -> CredentialRecord | None: ...

    def put(self, record: CredentialRecord) -> None: ...

    def delete(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str,
        credential_ref: str,
    ) -> bool: ...

    def list_for_tenant(self, tenant_id: str) -> list[CredentialRecord]: ...


class InMemorySecretRepository:
    """Development/test repository; production durability belongs to Phase 09."""

    def __init__(self) -> None:
        self.storage: dict[str, tuple[str, int]] = {}
        self._rotation_versions: dict[str, int] = {}

    @staticmethod
    def make_key(
        tenant_id: str,
        provider_id: str,
        credential_type: str,
        credential_ref: str,
    ) -> str:
        base = f"{tenant_id}:{provider_id}:{credential_type}"
        return base if credential_ref == "default" else f"{base}:{credential_ref}"

    def get(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str,
        credential_ref: str,
    ) -> CredentialRecord | None:
        key = self.make_key(tenant_id, provider_id, credential_type, credential_ref)
        stored = self.storage.get(key)
        if stored is None:
            return None
        blob, key_version = stored
        return CredentialRecord(
            tenant_id=tenant_id,
            provider_id=provider_id,
            credential_type=credential_type,
            credential_ref=credential_ref,
            encrypted_blob=blob,
            key_version=key_version,
            rotation_version=self._rotation_versions.get(key, 1),
        )

    def put(self, record: CredentialRecord) -> None:
        key = self.make_key(
            record.tenant_id,
            record.provider_id,
            record.credential_type,
            record.credential_ref,
        )
        self.storage[key] = (record.encrypted_blob, record.key_version)
        self._rotation_versions[key] = record.rotation_version

    def delete(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str,
        credential_ref: str,
    ) -> bool:
        key = self.make_key(tenant_id, provider_id, credential_type, credential_ref)
        existed = self.storage.pop(key, None) is not None
        self._rotation_versions.pop(key, None)
        return existed

    def list_for_tenant(self, tenant_id: str) -> list[CredentialRecord]:
        records: list[CredentialRecord] = []
        for key in sorted(self.storage):
            parts = key.split(":")
            if not parts or parts[0] != tenant_id or len(parts) < 3:
                continue
            provider_id, credential_type = parts[1], parts[2]
            credential_ref = parts[3] if len(parts) > 3 else "default"
            record = self.get(
                tenant_id, provider_id, credential_type, credential_ref
            )
            if record is not None:
                records.append(record)
        return records


class PostgresSecretRepository:
    """Async encrypted-credential persistence under tenant RLS."""

    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def get(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str,
        credential_ref: str,
    ) -> CredentialRecord | None:
        async with self.database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                "SELECT tenant_id::text, provider_id, credential_type, "
                "credential_ref, encrypted_blob, key_version, rotation_version, "
                "created_at, rotated_at "
                "FROM tenant_credentials WHERE tenant_id = %s::uuid "
                "AND provider_id = %s AND credential_type = %s "
                "AND credential_ref = %s",
                (tenant_id, provider_id, credential_type, credential_ref),
            )
            row = await cursor.fetchone()
        return CredentialRecord(*row) if row is not None else None

    async def put(self, record: CredentialRecord) -> None:
        async with self.database.tenant_transaction(record.tenant_id) as connection:
            await connection.execute(
                """
                INSERT INTO tenant_credentials (
                    tenant_id, provider_id, credential_type, credential_ref,
                    encrypted_blob, key_version, rotation_version, rotated_at
                ) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (
                    tenant_id, provider_id, credential_type, credential_ref
                ) DO UPDATE SET
                    encrypted_blob = EXCLUDED.encrypted_blob,
                    key_version = EXCLUDED.key_version,
                    rotation_version = EXCLUDED.rotation_version,
                    rotated_at = NOW()
                """,
                (
                    record.tenant_id,
                    record.provider_id,
                    record.credential_type,
                    record.credential_ref,
                    record.encrypted_blob,
                    record.key_version,
                    record.rotation_version,
                ),
            )

    async def delete(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str,
        credential_ref: str,
    ) -> bool:
        async with self.database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                "DELETE FROM tenant_credentials WHERE tenant_id = %s::uuid "
                "AND provider_id = %s AND credential_type = %s "
                "AND credential_ref = %s RETURNING id",
                (tenant_id, provider_id, credential_type, credential_ref),
            )
            return await cursor.fetchone() is not None

    async def list_for_tenant(self, tenant_id: str) -> list[CredentialRecord]:
        async with self.database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                "SELECT tenant_id::text, provider_id, credential_type, "
                "credential_ref, encrypted_blob, key_version, rotation_version, "
                "created_at, rotated_at FROM tenant_credentials "
                "WHERE tenant_id = %s::uuid "
                "ORDER BY provider_id, credential_type, credential_ref",
                (tenant_id,),
            )
            rows = await cursor.fetchall()
        return [CredentialRecord(*row) for row in rows]
