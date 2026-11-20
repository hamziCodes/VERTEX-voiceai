from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = REPO_ROOT / "infra" / "db" / "migrations" / "031_studio_customer_roles.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_phase13h_migration_constrains_both_human_role_columns() -> None:
    sql = _sql()

    assert "ALTER TABLE memberships" in sql
    assert "memberships_role_check" in sql
    assert "ALTER TABLE workspace_invitations" in sql
    assert "workspace_invitations_role_check" in sql
    for role in (
        "tenant_admin",
        "tenant_editor",
        "tenant_developer",
        "tenant_viewer",
        "compliance_admin",
    ):
        assert f"'{role}'" in sql


def test_phase13h_migration_does_not_add_deferred_platform_roles() -> None:
    sql = _sql()

    assert "platform_operations" not in sql
    assert "platform_auditor" not in sql
    assert "superadmin" not in sql
