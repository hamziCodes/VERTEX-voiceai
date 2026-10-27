from __future__ import annotations

from uuid import uuid4

import pytest

from post_call.webhook.legacy_migration import (
    InMemoryLegacyWebhookRepository,
    LegacyWebhookMigrationState,
    LegacyWebhookSecretMigrator,
)


class _Vault:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str, str]] = []
        self.fail = False

    async def astore(
        self,
        tenant_id: str,
        provider_id: str,
        secret: str,
        credential_type: str,
        *,
        credential_ref: str,
    ) -> object:
        if self.fail:
            raise RuntimeError("private vault detail")
        self.calls.append(
            (tenant_id, provider_id, secret, credential_type, credential_ref)
        )
        return object()


@pytest.mark.asyncio
async def test_legacy_secret_moves_to_vault_before_raw_value_is_wiped() -> None:
    tenant_id, target_id = uuid4(), uuid4()
    repository = InMemoryLegacyWebhookRepository()
    repository.seed(
        target_id=target_id,
        tenant_id=tenant_id,
        url="https://example.test/hook",
        secret="generated-legacy-fixture",
    )
    vault = _Vault()
    migrator = LegacyWebhookSecretMigrator(
        repository=repository, vault=vault, worker_id="legacy-a"
    )

    assert await migrator.run_once() is True
    row = await repository.get(target_id)
    assert row.state is LegacyWebhookMigrationState.MIGRATED
    assert row.secret is None
    assert row.credential_ref == f"legacy-webhook-{target_id}"
    assert row.enabled is False
    assert len(vault.calls) == 1
    replacement = repository.replacement_targets[target_id]
    assert replacement["credential_ref"] == row.credential_ref
    assert replacement["state"] == "pending"


@pytest.mark.asyncio
async def test_vault_failure_keeps_raw_value_for_retry_without_exposing_it() -> None:
    tenant_id, target_id = uuid4(), uuid4()
    repository = InMemoryLegacyWebhookRepository()
    repository.seed(
        target_id=target_id,
        tenant_id=tenant_id,
        url="https://example.test/hook",
        secret="generated-legacy-fixture",
    )
    vault = _Vault()
    vault.fail = True
    migrator = LegacyWebhookSecretMigrator(
        repository=repository, vault=vault, worker_id="legacy-a"
    )

    assert await migrator.run_once() is True
    row = await repository.get(target_id)
    assert row.state is LegacyWebhookMigrationState.FAILED
    assert row.secret == "generated-legacy-fixture"
    assert row.last_error_code == "vault_store_failed"
    assert "generated-legacy-fixture" not in repr(row)
    assert "private vault detail" not in repr(row)
    assert repository.replacement_targets == {}
