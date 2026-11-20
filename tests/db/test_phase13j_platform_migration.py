"""Phase 13J: static contract for migration 032 (platform staff roles)."""

from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "db"
    / "migrations"
    / "032_platform_staff_roles.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_platform_roles_are_constrained_to_the_two_launch_roles() -> None:
    sql = _sql()
    assert "CREATE TABLE IF NOT EXISTS platform_memberships" in sql
    assert "role IN ('platform_admin', 'platform_support')" in sql
    assert "reason TEXT NOT NULL" in sql
    assert "'*'" not in sql


def test_backfill_is_idempotent_and_audited() -> None:
    sql = _sql()
    assert "WHERE u.is_platform_admin = TRUE" in sql
    assert "ON CONFLICT (user_id) DO NOTHING" in sql
    assert "'platform_staff.migrated'" in sql


def test_platform_tables_are_hidden_from_the_tenant_app_role() -> None:
    sql = _sql()
    for table in ("platform_memberships", "platform_audit_events"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
        assert f"REVOKE ALL ON {table} FROM ucve_app" in sql
    assert "GRANT" not in sql.upper().replace("GRANTED", "")


def test_platform_audit_is_append_only() -> None:
    sql = _sql()
    assert "BEFORE UPDATE OR DELETE ON platform_audit_events" in sql
