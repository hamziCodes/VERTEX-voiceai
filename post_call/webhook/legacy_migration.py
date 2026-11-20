"""Restart-safe migration of quarantined legacy webhook signing secrets."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from core.db.async_pg import AsyncDatabase, get_default_database


class LegacyWebhookMigrationState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    MIGRATED = "migrated"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LegacyWebhookRow:
    target_id: UUID
    tenant_id: UUID
    url: str
    secret: str | None = field(default=None, repr=False)
    enabled: bool = False
    credential_ref: str | None = None
    state: LegacyWebhookMigrationState = LegacyWebhookMigrationState.PENDING
    last_error_code: str | None = None
    lease_owner: str | None = None


class InMemoryLegacyWebhookRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, LegacyWebhookRow] = {}
        self.replacement_targets: dict[UUID, dict[str, str]] = {}

    def seed(
        self,
        *,
        target_id: UUID,
        tenant_id: UUID,
        url: str,
        secret: str,
    ) -> None:
        self.rows[target_id] = LegacyWebhookRow(
            target_id=target_id,
            tenant_id=tenant_id,
            url=url,
            secret=secret,
        )

    async def get(self, target_id: UUID) -> LegacyWebhookRow:
        return self.rows[target_id]

    async def claim_next(self, worker_id: str) -> LegacyWebhookRow | None:
        for row in self.rows.values():
            if row.state not in {
                LegacyWebhookMigrationState.PENDING,
                LegacyWebhookMigrationState.FAILED,
            }:
                continue
            claimed = replace(
                row,
                state=LegacyWebhookMigrationState.RUNNING,
                lease_owner=worker_id,
                last_error_code=None,
                enabled=False,
            )
            self.rows[row.target_id] = claimed
            return claimed
        return None

    async def complete(
        self,
        target_id: UUID,
        *,
        worker_id: str,
        credential_ref: str,
    ) -> LegacyWebhookRow:
        row = self.rows[target_id]
        if row.lease_owner != worker_id:
            raise RuntimeError("Legacy webhook row lease is not owned by worker.")
        self.replacement_targets[target_id] = {
            "tenant_id": str(row.tenant_id),
            "url": row.url,
            "credential_ref": credential_ref,
            "state": "pending",
        }
        updated = replace(
            row,
            secret=None,
            enabled=False,
            credential_ref=credential_ref,
            state=LegacyWebhookMigrationState.MIGRATED,
            lease_owner=None,
            last_error_code=None,
        )
        self.rows[target_id] = updated
        return updated

    async def fail(
        self, target_id: UUID, *, worker_id: str, error_code: str
    ) -> LegacyWebhookRow:
        row = self.rows[target_id]
        if row.lease_owner != worker_id:
            raise RuntimeError("Legacy webhook row lease is not owned by worker.")
        updated = replace(
            row,
            enabled=False,
            state=LegacyWebhookMigrationState.FAILED,
            lease_owner=None,
            last_error_code=error_code[:64],
        )
        self.rows[target_id] = updated
        return updated


class PostgresLegacyWebhookRepository:
    """Lease one quarantined legacy target and replace it atomically."""

    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    @staticmethod
    def _from_row(row: Any) -> LegacyWebhookRow:
        return LegacyWebhookRow(
            target_id=row[0],
            tenant_id=row[1],
            url=row[2],
            secret=row[3],
            enabled=row[4],
            credential_ref=row[5],
            state=LegacyWebhookMigrationState(row[6]),
            last_error_code=row[7],
            lease_owner=row[8],
        )

    @staticmethod
    def _select() -> str:
        return (
            "id, tenant_id, url, secret, enabled, credential_ref, "
            "migration_state, migration_error_code, migration_lease_owner"
        )

    async def get(self, target_id: UUID) -> LegacyWebhookRow:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._select()
                + " FROM webhook_targets WHERE id = %s::uuid",
                (str(target_id),),
            )
            row = await cursor.fetchone()
        if row is None:
            raise KeyError(target_id)
        return self._from_row(row)

    async def claim_next(
        self, worker_id: str, *, now: datetime | None = None, lease_seconds: int = 60
    ) -> LegacyWebhookRow | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        timestamp = now or datetime.now(UTC)
        lease_expires = timestamp + timedelta(seconds=max(1, lease_seconds))
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT id FROM webhook_targets WHERE secret IS NOT NULL "
                "AND migration_attempt_count < migration_max_attempts AND "
                "(((migration_state IN ('pending', 'failed')) "
                "AND migration_available_at <= %s) OR "
                "(migration_state = 'running' AND migration_lease_expires_at <= %s)) "
                "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1",
                (timestamp, timestamp),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            updated = await connection.execute(
                "UPDATE webhook_targets SET enabled = FALSE, "
                "migration_state = 'running', migration_lease_owner = %s, "
                "migration_lease_expires_at = %s, migration_error_code = NULL "
                "WHERE id = %s::uuid RETURNING " + self._select(),
                (worker_id, lease_expires, str(row[0])),
            )
            claimed = await updated.fetchone()
        return self._from_row(claimed)

    async def complete(
        self, target_id: UUID, *, worker_id: str, credential_ref: str
    ) -> LegacyWebhookRow:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._select()
                + " FROM webhook_targets WHERE id = %s::uuid FOR UPDATE",
                (str(target_id),),
            )
            row = await cursor.fetchone()
            if row is None:
                raise KeyError(target_id)
            legacy = self._from_row(row)
            if (
                legacy.state is not LegacyWebhookMigrationState.RUNNING
                or legacy.lease_owner != worker_id
            ):
                raise RuntimeError("Legacy webhook row lease is not owned by worker.")
            await connection.execute(
                "INSERT INTO post_call_webhook_targets "
                "(target_id, tenant_id, name, url, credential_ref, state) VALUES "
                "(%s::uuid, %s::uuid, %s, %s, %s, 'pending') "
                "ON CONFLICT (target_id) DO UPDATE SET "
                "credential_ref = EXCLUDED.credential_ref, state = 'pending', "
                "updated_at = NOW()",
                (
                    str(legacy.target_id),
                    str(legacy.tenant_id),
                    f"Migrated legacy target {str(legacy.target_id)[:8]}",
                    legacy.url,
                    credential_ref,
                ),
            )
            updated = await connection.execute(
                "UPDATE webhook_targets SET secret = NULL, enabled = FALSE, "
                "credential_ref = %s, migration_state = 'migrated', "
                "migrated_at = NOW(), migration_error_code = NULL, "
                "migration_lease_owner = NULL, migration_lease_expires_at = NULL "
                "WHERE id = %s::uuid RETURNING " + self._select(),
                (credential_ref, str(target_id)),
            )
            completed = await updated.fetchone()
        return self._from_row(completed)

    async def fail(
        self,
        target_id: UUID,
        *,
        worker_id: str,
        error_code: str,
        now: datetime | None = None,
    ) -> LegacyWebhookRow:
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT migration_attempt_count, migration_max_attempts, "
                "migration_lease_owner FROM webhook_targets "
                "WHERE id = %s::uuid FOR UPDATE",
                (str(target_id),),
            )
            row = await cursor.fetchone()
            if row is None:
                raise KeyError(target_id)
            if row[2] != worker_id:
                raise RuntimeError("Legacy webhook row lease is not owned by worker.")
            attempt = row[0] + 1
            available = timestamp + timedelta(seconds=min(300, 2 ** (attempt - 1)))
            updated = await connection.execute(
                "UPDATE webhook_targets SET enabled = FALSE, "
                "migration_state = 'failed', "
                "migration_attempt_count = %s, migration_available_at = %s, "
                "migration_error_code = %s, migration_lease_owner = NULL, "
                "migration_lease_expires_at = NULL WHERE id = %s::uuid RETURNING "
                + self._select(),
                (attempt, available, error_code[:64], str(target_id)),
            )
            failed = await updated.fetchone()
        return self._from_row(failed)


class LegacyWebhookSecretMigrator:
    def __init__(self, *, repository: Any, vault: Any, worker_id: str) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        self.repository = repository
        self.vault = vault
        self.worker_id = worker_id

    async def run_once(self) -> bool:
        row = await self.repository.claim_next(self.worker_id)
        if row is None:
            return False
        if not row.secret:
            await self.repository.fail(
                row.target_id,
                worker_id=self.worker_id,
                error_code="legacy_secret_missing",
            )
            return True
        credential_ref = f"legacy-webhook-{row.target_id}"
        try:
            await self.vault.astore(
                str(row.tenant_id),
                "webhook",
                row.secret,
                "hmac_secret",
                credential_ref=credential_ref,
            )
        except Exception:
            await self.repository.fail(
                row.target_id,
                worker_id=self.worker_id,
                error_code="vault_store_failed",
            )
            return True
        await self.repository.complete(
            row.target_id,
            worker_id=self.worker_id,
            credential_ref=credential_ref,
        )
        return True
