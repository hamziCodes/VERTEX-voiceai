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
    assert migrations.is_dir()
    assert (migrations / "001_core_tenant_schema.sql").is_file()
    assert (migrations / "002_rls_policies.sql").is_file()
    assert (REPO_ROOT / "infra" / "db" / "seed" / "dev_tenant.sql").is_file()


@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_read(db_module) -> None:
    tenant_repo = db_module.repos.TenantRepository()

    tenant_a = db_module.Tenant(id="tenant-a", name="Tenant A")
    tenant_b = db_module.Tenant(id="tenant-b", name="Tenant B")
    await tenant_repo.create_tenant(tenant_a)
    await tenant_repo.create_tenant(tenant_b)

    agent_b = db_module.Agent(id="agent-b", tenant_id="tenant-b", name="Agent B")
    await tenant_repo.save_agent(agent_b)

    # Tenant A attempts to fetch Tenant B's agent -> fails closed with PermissionError
    with pytest.raises(PermissionError):
        await tenant_repo.get_agent_for_tenant(
            tenant_id="tenant-a", agent_id="agent-b"
        )


@pytest.mark.asyncio
async def test_session_context_factory_bridges_tenant_id(db_module) -> None:
    factory = db_module.session_context_factory
    turn_ctx = factory(tenant_id="tenant-xyz", session_id="session-123", current_language="ur")

    assert turn_ctx.tenant_id == "tenant-xyz"
    assert turn_ctx.session_id == "session-123"
    assert turn_ctx.current_language == "ur"


@pytest.mark.asyncio
async def test_agent_provider_config_validation_on_write(db_module) -> None:
    agent_repo = db_module.repos.AgentRepository()
    from core.providers.exceptions import ConfigurationError

    # Single provider chain -> rejected on write
    invalid_agent = db_module.Agent(
        id="agent-bad",
        tenant_id="tenant-1",
        name="Bad Agent",
        agent_provider_config={
            "allow_testing_providers": True,
            "chains": [{"category": "stt", "language": "en", "priority": ["gladia"]}],
        },
    )
    with pytest.raises(ConfigurationError):
        await agent_repo.save_agent("tenant-1", invalid_agent)

    # Valid chain -> saved successfully
    valid_agent = db_module.Agent(
        id="agent-good",
        tenant_id="tenant-1",
        name="Good Agent",
        agent_provider_config={
            "allow_testing_providers": True,
            "chains": [{"category": "stt", "language": "en", "priority": ["null_stt_1", "null_stt_2"]}],
        },
    )
    saved = await agent_repo.save_agent("tenant-1", valid_agent, tenant_allow_testing=True)
    assert saved.id == "agent-good"


@pytest.mark.asyncio
async def test_missing_tenant_context_fails_closed(db_module) -> None:
    agent_repo = db_module.repos.AgentRepository()
    with pytest.raises(PermissionError):
        await agent_repo.get_agent(tenant_id="", agent_id="agent-123")


def test_s3_storage_client_recording_pointer() -> None:
    from core.storage.s3_client import S3StorageClient

    s3 = S3StorageClient(bucket_name="ucve-test-recordings")
    audio_data = b"RIFF....WAVEfmt ....data...."

    s3_uri, checksum, size = s3.upload_recording(
        tenant_id="tenant-1", session_id="session-1", audio_bytes=audio_data
    )

    assert s3_uri == "s3://ucve-test-recordings/tenant-1/session-1/recording.wav"
    assert size == len(audio_data)
    assert len(checksum) == 64

    downloaded = s3.download_recording(s3_uri)
    assert downloaded == audio_data

