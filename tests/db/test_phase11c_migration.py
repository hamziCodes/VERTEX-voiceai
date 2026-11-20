from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = REPO_ROOT / "infra" / "db" / "migrations" / "026_webhook_delivery.sql"


def test_webhook_delivery_migration_has_durable_security_contracts() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists post_call_webhook_targets" in sql
    assert "credential_ref" in sql
    assert "shared_secret" not in sql
    assert "create table if not exists webhook_deliveries" in sql
    assert "create table if not exists webhook_delivery_attempts" in sql
    assert "unique (tenant_id, target_id, call_id, event_type)" in sql
    assert "enable row level security" in sql
    assert "force row level security" in sql
    assert "response_body" not in sql
