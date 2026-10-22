"""Encrypted tenant-secret repository contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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
