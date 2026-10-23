from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "db"
    / "migrations"
    / "022_knowledge_runtime.sql"
)


def test_knowledge_migration_defines_durable_domain_and_rls() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    for table in (
        "knowledge_bases",
        "knowledge_sources",
        "knowledge_ingestion_jobs",
        "agent_knowledge_bindings",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
        assert "WITH CHECK" in sql
    assert "vector(384)" in sql
    assert "legacy_knowledge_chunks_require_reingestion" in sql
    assert "knowledge_base_id" in sql
    assert "citation_jsonb" in sql
    assert "embedding_model" in sql
    assert "FOREIGN KEY (tenant_id, knowledge_base_id)" in sql
    assert "FOREIGN KEY (tenant_id, agent_version_id)" in sql


def test_knowledge_migration_has_bounded_states_and_idempotency() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "knowledge_base_status_check" in sql
    assert "knowledge_source_status_check" in sql
    assert "knowledge_job_state_check" in sql
    assert "UNIQUE (tenant_id, knowledge_base_id, checksum_sha256, revision)" in sql
    assert "UNIQUE (tenant_id, idempotency_key)" in sql
    assert "UNIQUE (tenant_id, agent_version_id, knowledge_base_id)" in sql
    assert "UNIQUE (tenant_id, agent_id, knowledge_base_id, knowledge_revision)" in sql
