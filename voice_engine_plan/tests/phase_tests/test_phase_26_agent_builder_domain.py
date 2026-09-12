"""Phase 26: Self-Serve Agent Builder Domain Model Test Suite."""

from __future__ import annotations

import json
from pathlib import Path
import time
from uuid import uuid4

import pytest

from control_plane.agents import (
    AgentConfig,
    AgentConfigRepo,
    AgentConfigValidator,
    AgentNotFoundError,
    AgentProvidersConfig,
    CategoryPriorityChain,
    PersonaConfig,
    ProviderRoute,
    SessionConfigPin,
)
from control_plane.agents.templates import list_templates, load_template

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_26_self_serve_agent_builder_domain_model.md"
)


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_autosave_and_config_pin_documented() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "autosave" in text.lower()
    assert "pin" in text.lower()
    assert "[LATER]" in text
    assert "None — fully deterministic" in text


def test_valid_config_passes_validator() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    config = AgentConfig(
        agent_id=agent_id,
        tenant_id=tenant_id,
        name="Valid Support Agent",
        persona=PersonaConfig(
            system_prompt="Helpful assistant",
            greeting="Hello",
            voice_id="cartesia-sonic-en",
        ),
        languages=["en"],
        providers=AgentProvidersConfig.create_default(),
    )
    validator = AgentConfigValidator()
    result = validator.validate(config)
    assert result.is_valid
    assert len(result.errors) == 0


def test_single_provider_chain_rejected() -> None:
    tenant_id = uuid4()
    # Provide only 1 route for LLM (violating resilience rule of >= 2)
    single_route_providers = AgentProvidersConfig(
        stt=[
            CategoryPriorityChain(
                category="stt",
                language="en",
                routes=[
                    ProviderRoute(provider_id="gladia", priority=1, enabled=True),
                    ProviderRoute(provider_id="whisper", priority=2, enabled=True),
                ],
            )
        ],
        llm=[
            CategoryPriorityChain(
                category="llm",
                language="en",
                routes=[
                    ProviderRoute(provider_id="groq", priority=1, enabled=True)
                ],
            )
        ],
        tts=[
            CategoryPriorityChain(
                category="tts",
                language="en",
                routes=[
                    ProviderRoute(provider_id="cartesia", priority=1, enabled=True),
                    ProviderRoute(provider_id="uplift", priority=2, enabled=True),
                ],
            )
        ],
    )
    config = AgentConfig(
        tenant_id=tenant_id,
        name="Single Provider Test",
        providers=single_route_providers,
    )
    validator = AgentConfigValidator()
    result = validator.validate(config)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "INSUFFICIENT_PROVIDER_ROUTES" in codes


def test_arabic_without_rtl_voice_rejected() -> None:
    tenant_id = uuid4()
    # Configure Arabic language but with standard English-only voice
    config = AgentConfig(
        tenant_id=tenant_id,
        name="Arabic Agent Non-RTL Voice",
        languages=["ar"],
        persona=PersonaConfig(voice_id="american-english-female-1"),
        providers=AgentProvidersConfig.create_default(),
    )
    validator = AgentConfigValidator()
    result = validator.validate(config)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "ARABIC_RTL_VOICE_REQUIRED" in codes

    # Now fix to valid Arabic RTL voice
    config.persona.voice_id = "ar-sa-naima"
    result2 = validator.validate(config)
    assert result2.is_valid


def test_max_fields_extraction_rejected() -> None:
    tenant_id = uuid4()
    # Generate 55 fields exceeding 50 limit
    oversized_fields = {f"field_{i}": {"type": "string"} for i in range(55)}
    config = AgentConfig(
        tenant_id=tenant_id,
        name="Oversized Extraction Agent",
        extraction_schema={"fields": oversized_fields},
        providers=AgentProvidersConfig.create_default(),
    )
    validator = AgentConfigValidator()
    result = validator.validate(config)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "EXTRACTION_FIELD_CAP_EXCEEDED" in codes


def test_publish_creates_immutable_version() -> None:
    tenant_id = uuid4()
    repo = AgentConfigRepo()
    agent = AgentConfig(tenant_id=tenant_id, name="Publishable Agent")
    repo.create_agent(agent)

    published_v1, _ = repo.publish(tenant_id, agent.agent_id, published_by="admin")
    assert published_v1.version == 1
    assert published_v1.is_published

    # Modify draft and publish v2
    repo.save_draft_autosave(
        tenant_id,
        agent.agent_id,
        {"description": "Updated description for v2"},
        force=True,
    )
    published_v2, _ = repo.publish(tenant_id, agent.agent_id, published_by="admin")
    assert published_v2.version == 2

    # Fetching v1 snapshot must be unmodified
    snapshot_v1 = repo.get_published_version(tenant_id, agent.agent_id, version=1)
    assert snapshot_v1.description == ""
    assert snapshot_v1.version == 1

    snapshot_v2 = repo.get_published_version(tenant_id, agent.agent_id, version=2)
    assert snapshot_v2.description == "Updated description for v2"
    assert snapshot_v2.version == 2


def test_session_pin_loads_pinned_version_not_draft() -> None:
    tenant_id = uuid4()
    repo = AgentConfigRepo()
    agent = AgentConfig(tenant_id=tenant_id, name="Pinned Agent")
    repo.create_agent(agent)
    repo.publish(tenant_id, agent.agent_id)

    pin_engine = SessionConfigPin(repo)
    session_id = uuid4()
    pinned = pin_engine.pin_session(session_id, tenant_id, agent.agent_id)
    assert pinned.version == 1

    # Edit draft after pinning
    repo.save_draft_autosave(
        tenant_id,
        agent.agent_id,
        {"name": "Draft Edited Mid-Call"},
        force=True,
    )

    # Active session still loads pinned snapshot, NOT draft
    active = pin_engine.get_pinned_config(session_id)
    assert active is not None
    assert active.name == "Pinned Agent"


def test_concurrent_publish_does_not_affect_active_session_pin() -> None:
    tenant_id = uuid4()
    repo = AgentConfigRepo()
    agent = AgentConfig(tenant_id=tenant_id, name="Stable Agent v1")
    repo.create_agent(agent)
    repo.publish(tenant_id, agent.agent_id)

    pin_engine = SessionConfigPin(repo)
    session_id = uuid4()
    pin_engine.pin_session(session_id, tenant_id, agent.agent_id)

    # Concurrently publish v2 while session is live
    repo.save_draft_autosave(
        tenant_id,
        agent.agent_id,
        {"name": "Stable Agent v2 (Live Edit)"},
        force=True,
    )
    repo.publish(tenant_id, agent.agent_id)

    # Pinned session remains on v1 snapshot
    active = pin_engine.get_pinned_config(session_id)
    assert active is not None
    assert active.version == 1
    assert active.name == "Stable Agent v1"


def test_autosave_debounce_writes_draft() -> None:
    tenant_id = uuid4()
    repo = AgentConfigRepo()
    agent = AgentConfig(tenant_id=tenant_id, name="Autosave Agent")
    repo.create_agent(agent)

    # First autosave immediately after creation should be debounced if debounce_seconds is large
    updated, saved = repo.save_draft_autosave(
        tenant_id,
        agent.agent_id,
        {"description": "Rapid edit"},
        debounce_seconds=30.0,
        force=False,
    )
    assert not saved
    assert updated.description == ""

    # Force autosave bypasses debounce
    updated_forced, saved_forced = repo.save_draft_autosave(
        tenant_id,
        agent.agent_id,
        {"description": "Forced edit"},
        force=True,
    )
    assert saved_forced
    assert updated_forced.description == "Forced edit"


def test_json_schema_export_matches_pydantic_model() -> None:
    schema_file = REPO_ROOT / "schemas" / "agent-config-v1.json"
    assert schema_file.is_file()
    disk_schema = json.loads(schema_file.read_text(encoding="utf-8"))
    model_schema = AgentConfig.model_json_schema()

    assert disk_schema.get("title") == model_schema.get("title")
    assert "properties" in disk_schema
    assert "persona" in disk_schema["properties"]
    assert "providers" in disk_schema["properties"]


def test_tenant_a_cannot_read_tenant_b_agent() -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    repo = AgentConfigRepo()
    agent_a = AgentConfig(tenant_id=tenant_a, name="Tenant A Secret Agent")
    repo.create_agent(agent_a)

    # Tenant B tries to read Tenant A's draft
    with pytest.raises(AgentNotFoundError):
        repo.get_draft(tenant_b, agent_a.agent_id)

    # Tenant B listing agents gets empty list
    agents_b = repo.list_agents(tenant_b)
    assert len(agents_b) == 0


def test_validate_and_publish_latency_under_50ms() -> None:
    tenant_id = uuid4()
    repo = AgentConfigRepo()
    agent = AgentConfig(tenant_id=tenant_id, name="Performance Benchmark Agent")
    repo.create_agent(agent)

    t0 = time.perf_counter()
    published, _ = repo.publish(tenant_id, agent.agent_id)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert published.is_published
    assert elapsed_ms < 50.0  # Under 50 ms target


def test_platform_seed_templates() -> None:
    templates = list_templates()
    assert "retail_customer_service" in templates
    assert "clinic_intake" in templates

    retail = load_template("retail_customer_service")
    assert retail["name"]
    clinic = load_template("clinic_intake")
    assert clinic["compliance"]["tier"] == "hipaa"
