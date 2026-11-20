from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = REPO_ROOT / "infra" / "db" / "migrations" / "030_studio_control_plane.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_phase13_migration_declares_identity_and_workspace_contracts() -> None:
    sql = _sql()

    assert "CREATE TABLE external_identities" in sql
    assert "UNIQUE (issuer, subject)" in sql
    assert "CREATE TABLE workspace_invitations" in sql
    assert "token_hash CHAR(64) NOT NULL UNIQUE" in sql
    assert "CREATE TABLE tenant_onboarding_profiles" in sql
    assert "CREATE TABLE tenant_entitlements" in sql
    assert "ADD COLUMN IF NOT EXISTS draft_revision BIGINT NOT NULL DEFAULT 1" in sql
    assert "ALTER COLUMN password_hash DROP NOT NULL" in sql
    assert "ALTER COLUMN email DROP NOT NULL" in sql
    assert "is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE" in sql


def test_phase13_migration_forces_tenant_rls_and_hides_identity_mapping() -> None:
    sql = _sql()

    for table in (
        "workspace_invitations",
        "tenant_onboarding_profiles",
        "tenant_entitlements",
    ):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
        assert f"CREATE POLICY {table}_tenant_isolation" in sql

    assert "REVOKE ALL ON external_identities FROM ucve_app" in sql
    assert "plaintext_token" not in sql
    assert "invitation_token TEXT" not in sql
