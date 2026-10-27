from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "db"
    / "migrations"
    / "027_privacy_deletion.sql"
)


def test_privacy_migration_defines_restart_safe_and_legacy_quarantine_contracts() -> (
    None
):
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists privacy_deletion_jobs" in sql
    assert "completed_object_refs" in sql
    assert "legal_hold" in sql
    assert "credential_ref" in sql
    assert "migration_state" in sql
    assert "update webhook_targets set enabled = false" in " ".join(sql.split())
    assert "force row level security" in sql
