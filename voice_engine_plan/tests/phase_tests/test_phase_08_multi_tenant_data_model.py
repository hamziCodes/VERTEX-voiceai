"""Phase 08: Multi-Tenant Core Data Model."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def db_module():
    try:
        from core import db  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 08 implementation pending: {exc}")
    return db


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_08_multi_tenant_core_data_model_and_isolation_boundaries.md"
    )
    assert plan.is_file()


def test_migration_files_exist() -> None:
    migrations = REPO_ROOT / "infra" / "db" / "migrations"
    if not migrations.is_dir():
        pytest.skip("Migrations not scaffolded yet")
    assert (migrations / "001_core_tenant_schema.sql").is_file()


@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_read(db_module) -> None:
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")

    tenant_repo = db_module.repos.tenant_repo
    with pytest.raises(PermissionError):
        await tenant_repo.get_agent_for_tenant(
            tenant_id="tenant-a", agent_id="agent-owned-by-tenant-b"
        )
