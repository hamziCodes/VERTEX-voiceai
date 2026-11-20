"""Phase 13K: static contract for migration 033 (support sessions)."""

from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "db"
    / "migrations"
    / "033_platform_support_sessions.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_support_sessions_are_bounded_reasoned_and_read_only() -> None:
    sql = _sql()
    assert "CREATE TABLE IF NOT EXISTS platform_support_sessions" in sql
    assert "ARRAY['configuration', 'readiness']" in sql
    assert "INTERVAL '60 minutes'" in sql
    assert "char_length(btrim(reason)) BETWEEN 8 AND 500" in sql
    for forbidden in ("write", "transcript", "recording", "credential"):
        assert f"'{forbidden}" not in sql


def test_platform_audit_records_support_activity() -> None:
    sql = _sql()
    for action in (
        "platform_support.session_started",
        "platform_support.session_ended",
        "platform_support.data_viewed",
    ):
        assert f"'{action}'" in sql
    assert "ADD COLUMN IF NOT EXISTS support_session_id UUID" in sql
    assert "ADD COLUMN IF NOT EXISTS scope TEXT" in sql


def test_support_sessions_are_hidden_from_the_tenant_app_role() -> None:
    sql = _sql()
    assert "ALTER TABLE platform_support_sessions ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE platform_support_sessions FORCE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON platform_support_sessions FROM ucve_app" in sql
