from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    REPO_ROOT / "infra" / "db" / "migrations" / "025_post_call_intelligence_jobs.sql"
)
REPOSITORY = REPO_ROOT / "post_call" / "jobs" / "repository.py"


def test_phase11b_migration_declares_outbox_results_review_and_rls() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for fragment in (
        "intelligence_config_snapshot",
        "create table if not exists post_call_jobs",
        "post_call_jobs_state_check",
        "create table if not exists post_call_intelligence_results",
        "create table if not exists post_call_review_requests",
        "unique (tenant_id, call_id, job_type)",
        "force row level security",
        "with check",
    ):
        assert fragment in sql

    repository = REPOSITORY.read_text(encoding="utf-8").lower()
    assert "for update skip locked" in repository
