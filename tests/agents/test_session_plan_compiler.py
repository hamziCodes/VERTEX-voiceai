"""Phase 06 immutable published-agent session compiler tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from control_plane.agents.compiler import (
    SessionPlanCompilationError,
    compile_agent_version,
)
from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.models.persona import PersonaConfig
from control_plane.agents.models.provider_config import (
    AgentProvidersConfig,
    CategoryPriorityChain,
    ProviderRoute,
)
from control_plane.agents.repo import AgentConfigRepo
from core.runtime.session_plan import (
    SESSION_PLAN_SCHEMA_VERSION,
    RuntimeSessionPlan,
    SessionPlanIntegrityError,
)
from core.secrets.policy import CredentialTier


def _chain(
    category: str,
    language: str,
    providers: tuple[tuple[str, str | None, str | None], ...],
) -> CategoryPriorityChain:
    return CategoryPriorityChain(
        category=category,
        language=language,
        routes=[
            ProviderRoute(
                provider_id=provider_id,
                model=model,
                credential_ref=credential_ref,
                credential_tier=CredentialTier.BYOK,
                priority=index,
            )
            for index, (provider_id, model, credential_ref) in enumerate(
                providers, start=1
            )
        ],
    )


def make_config(
    tenant_id: UUID,
    agent_id: UUID,
    *,
    prompt: str = "Published clinic assistant",
    languages: tuple[str, ...] = ("en",),
) -> AgentConfig:
    stt = []
    llm = []
    tts = []
    for language in languages:
        stt.append(
            _chain(
                "stt",
                language,
                (
                    ("gladia", None, "cred/stt-primary"),
                    ("deepgram", None, "cred/stt-secondary"),
                ),
            )
        )
        llm.append(
            _chain(
                "llm",
                language,
                (
                    ("groq", "openai/gpt-oss-120b", "cred/llm-primary"),
                    ("gemini", "gemini-2.5-flash", "cred/llm-secondary"),
                ),
            )
        )
        tts.append(
            _chain(
                "tts",
                language,
                (
                    ("cartesia", "sonic-2", "cred/tts-primary"),
                    ("uplift", "orator", "cred/tts-secondary"),
                ),
            )
        )
    return AgentConfig(
        agent_id=agent_id,
        tenant_id=tenant_id,
        name="Clinic",
        persona=PersonaConfig(
            system_prompt=prompt,
            greeting="Welcome to the clinic",
            voice_id="voice-primary",
            voice_by_language={language: f"voice-{language}" for language in languages},
        ),
        languages=list(languages),
        providers=AgentProvidersConfig(stt=stt, llm=llm, tts=tts),
        tools=[{"id": "book_appointment", "kind": "function"}],
        knowledge_bases=[{"id": "clinic-faq"}],
        extraction_schema_id="clinic-intake-v1",
        extraction_schema={"fields": [{"name": "appointment_date"}]},
        telephony={"inbound": True},
        compliance={"tier": "standard", "hipaa_baa_acknowledged": False},
        session_limits={"max_duration_sec": 1800, "max_turns": 120},
    )


def publish(repo: AgentConfigRepo, config: AgentConfig) -> AgentConfig:
    repo.create_agent(config)
    published, _ = repo.publish(config.tenant_id, config.agent_id)
    return published


def test_compiler_builds_deterministic_immutable_secret_free_plan() -> None:
    repo = AgentConfigRepo()
    tenant_id = uuid4()
    agent_id = uuid4()
    publish(repo, make_config(tenant_id, agent_id, languages=("en", "ur")))

    first = compile_agent_version(tenant_id, agent_id, 1, repo=repo)
    second = compile_agent_version(tenant_id, agent_id, 1, repo=repo)

    assert first == second
    assert len(first.plan_hash) == 64
    assert first.allowed_languages == ("en", "ur")
    assert first.primary_route("llm", "ur").provider_id == "groq"
    assert first.primary_route("llm", "ur").credential_tier == "byok"
    assert SESSION_PLAN_SCHEMA_VERSION == "1.1.0"
    assert first.voice_for_language("ur") == "voice-ur"
    assert first.credential_references == (
        "cred/llm-primary",
        "cred/llm-secondary",
        "cred/stt-primary",
        "cred/stt-secondary",
        "cred/tts-primary",
        "cred/tts-secondary",
    )
    assert "book_appointment" in first.tool_allowlist
    assert "clinic-faq" in first.knowledge_base_ids
    with pytest.raises(ValidationError):
        first.system_prompt = "mutated"  # type: ignore[misc]


def test_snapshot_round_trip_rejects_hash_tampering() -> None:
    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4())
    publish(repo, config)
    plan = compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)

    restored = RuntimeSessionPlan.from_snapshot(plan.to_snapshot())
    assert restored == plan

    tampered = plan.to_snapshot()
    tampered["system_prompt"] = "attacker prompt"
    with pytest.raises(SessionPlanIntegrityError, match="hash"):
        RuntimeSessionPlan.from_snapshot(tampered)


def test_compiler_rejects_plaintext_credentials_and_unknown_provider() -> None:
    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4())
    config.tools = [{"id": "unsafe", "api_key": "must-never-enter-plan"}]
    publish(repo, config)

    with pytest.raises(SessionPlanCompilationError) as secret_error:
        compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)
    assert secret_error.value.code == "PLAINTEXT_CREDENTIAL_FORBIDDEN"

    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4())
    config.providers.stt[0].routes[0].provider_id = "unknown-stt"
    publish(repo, config)
    with pytest.raises(SessionPlanCompilationError) as provider_error:
        compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)
    assert provider_error.value.code == "PROVIDER_UNSUPPORTED"


def test_compiler_rejects_unpublished_cross_tenant_and_missing_language_chain() -> None:
    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4())
    repo.create_agent(config)
    with pytest.raises(SessionPlanCompilationError) as unpublished:
        compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)
    assert unpublished.value.code == "PUBLISHED_CONFIG_NOT_FOUND"

    publish(repo, config)
    with pytest.raises(SessionPlanCompilationError) as cross_tenant:
        compile_agent_version(uuid4(), config.agent_id, 1, repo=repo)
    assert cross_tenant.value.code == "PUBLISHED_CONFIG_NOT_FOUND"

    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4(), languages=("en", "ur"))
    config.providers.tts = [config.providers.tts[0]]
    publish(repo, config)
    with pytest.raises(SessionPlanCompilationError) as missing_chain:
        compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)
    assert missing_chain.value.code == "PROVIDER_CHAIN_MISSING"


def test_publish_during_call_and_rollback_keep_version_snapshots_stable() -> None:
    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4(), prompt="version one")
    publish(repo, config)
    v1 = compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)

    repo.save_draft_autosave(
        config.tenant_id,
        config.agent_id,
        {"persona": {**config.persona.model_dump(), "system_prompt": "version two"}},
        force=True,
    )
    repo.publish(config.tenant_id, config.agent_id)
    v2 = compile_agent_version(config.tenant_id, config.agent_id, 2, repo=repo)
    v1_again = compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)

    assert v1.system_prompt == "version one"
    assert v2.system_prompt == "version two"
    assert v1_again.plan_hash == v1.plan_hash
    assert v2.plan_hash != v1.plan_hash


def test_session_selection_is_limited_to_published_languages_and_voice_mapping() -> (
    None
):
    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4(), languages=("en", "ur"))
    publish(repo, config)
    plan = compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)

    selection = plan.select(language="ur", voice_id="voice-ur")
    assert selection.language == "ur"
    assert selection.voice_id == "voice-ur"

    with pytest.raises(ValueError, match="language"):
        plan.select(language="fr")
    with pytest.raises(ValueError, match="voice"):
        plan.select(language="ur", voice_id="other-voice")


@pytest.mark.parametrize("tier", ["byok", "both"])
def test_compiler_requires_reference_for_tenant_credential_tiers(tier: str) -> None:
    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4())
    route = config.providers.llm[0].routes[0]
    route.credential_tier = CredentialTier(tier)
    route.credential_ref = None
    publish(repo, config)

    with pytest.raises(SessionPlanCompilationError) as error:
        compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)

    assert error.value.code == "CREDENTIAL_REFERENCE_REQUIRED"


def test_compiler_rejects_tenant_reference_for_platform_tier() -> None:
    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4())
    route = config.providers.stt[0].routes[0]
    route.credential_tier = CredentialTier.PLATFORM
    publish(repo, config)

    with pytest.raises(SessionPlanCompilationError) as error:
        compile_agent_version(config.tenant_id, config.agent_id, 1, repo=repo)

    assert error.value.code == "PLATFORM_CREDENTIAL_REFERENCE_FORBIDDEN"


def test_credential_tier_is_signed_into_plan_hash() -> None:
    repo = AgentConfigRepo()
    config = make_config(uuid4(), uuid4())
    publish(repo, config)
    byok_plan = compile_agent_version(
        config.tenant_id, config.agent_id, 1, repo=repo
    )

    snapshot = byok_plan.to_snapshot()
    snapshot["provider_chains"][0]["routes"][0]["credential_tier"] = "both"
    with pytest.raises(SessionPlanIntegrityError, match="hash"):
        RuntimeSessionPlan.from_snapshot(snapshot)
