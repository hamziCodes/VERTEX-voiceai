"""Phase 06 published plan mint-to-worker authority tests."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest

from control_plane.agents.repo import AgentConfigRepo
from control_plane.auth.hmac_mint import expected_signature
from control_plane.auth.jwt import verify_session_jwt
from control_plane.routes.session import MintContext, handle_session_mint
from core.db.models import Agent, Tenant
from core.language.router import LanguageRouter
from core.redis.nonce_store import NonceStore
from tests.agents.test_session_plan_compiler import make_config, publish
from worker_raw.main import SessionPlanLoadError, _load_session_config
from worker_raw.orchestration.session_config import PipelineSessionConfig
from worker_raw.orchestration.tool_handler import PipelineToolHandler
from worker_raw.ws_session import WebSocketSessionRunner


async def _seed_context(
    *, languages: tuple[str, ...] = ("en",)
) -> tuple[MintContext, str, str]:
    tenant_id = str(uuid4())
    agent_id = str(uuid4())
    repo = AgentConfigRepo()
    publish(
        repo,
        make_config(uuid4_from(tenant_id), uuid4_from(agent_id), languages=languages),
    )
    ctx = MintContext(agent_config_repo=repo)
    await ctx.tenant_repo.create_tenant(Tenant(id=tenant_id, name="Tenant"))
    await ctx.tenant_repo.save_agent(
        Agent(id=agent_id, tenant_id=tenant_id, name="Agent")
    )
    return ctx, tenant_id, agent_id


def uuid4_from(value: str) -> UUID:
    return UUID(value)


async def _mint(
    ctx: MintContext,
    tenant_id: str,
    agent_id: str,
    nonce: str,
    *,
    language: str | None = None,
) -> tuple[int, dict[str, object]]:
    secret = "phase-six-test-secret"
    timestamp = str(int(time.time()))
    signature = expected_signature(secret, tenant_id, timestamp, nonce, agent_id)
    return await handle_session_mint(
        tenant_id,
        timestamp,
        nonce,
        agent_id,
        signature,
        secret=secret,
        ctx=ctx,
        requested_language=language,
    )


@pytest.mark.asyncio
async def test_mint_pins_signed_plan_reference_and_worker_loads_it() -> None:
    ctx, tenant_id, agent_id = await _seed_context(languages=("en", "ur"))

    status, body = await _mint(
        ctx, tenant_id, agent_id, "published-plan-1", language="ur"
    )

    assert status == 200
    payload = verify_session_jwt(str(body["token"]))
    assert payload["agent_config_version"] == 1
    assert len(payload["session_plan_hash"]) == 64
    assert payload["session_language"] == "ur"
    session = await ctx.session_repo.get_session(tenant_id, str(body["session_id"]))
    assert session is not None
    assert session.runtime_plan_snapshot["plan_hash"] == payload["session_plan_hash"]

    config = await _load_session_config(payload, mint_context=ctx)
    assert config.plan_authoritative is True
    assert config.agent_config_version == 1
    assert config.system_prompt == "Published clinic assistant"
    assert config.language == "ur"
    assert config.tts_voice_id == "voice-ur"
    assert config.stt_provider == "gladia"
    assert config.llm_provider == "groq"
    assert config.tts_provider == "cartesia"
    assert config.tool_allowlist == ("book_appointment",)
    assert config.knowledge_base_ids == ("clinic-faq",)
    assert config.extraction_schema_id == "clinic-intake-v1"
    assert config.telephony_policy == {"inbound": True}


@pytest.mark.asyncio
async def test_active_session_stays_on_v1_after_v2_publish_and_new_mint_uses_v2() -> (
    None
):
    ctx, tenant_id, agent_id = await _seed_context()
    status, first = await _mint(ctx, tenant_id, agent_id, "pin-v1")
    assert status == 200
    first_payload = verify_session_jwt(str(first["token"]))

    from uuid import UUID

    draft = ctx.agent_config_repo.get_draft(UUID(tenant_id), UUID(agent_id))
    ctx.agent_config_repo.save_draft_autosave(
        UUID(tenant_id),
        UUID(agent_id),
        {
            "persona": {
                **draft.persona.model_dump(),
                "system_prompt": "Published version two",
            }
        },
        force=True,
    )
    ctx.agent_config_repo.publish(UUID(tenant_id), UUID(agent_id))

    old_config = await _load_session_config(first_payload, mint_context=ctx)
    status, second = await _mint(ctx, tenant_id, agent_id, "pin-v2")
    assert status == 200
    second_payload = verify_session_jwt(str(second["token"]))
    new_config = await _load_session_config(second_payload, mint_context=ctx)

    assert old_config.agent_config_version == 1
    assert old_config.system_prompt == "Published clinic assistant"
    assert new_config.agent_config_version == 2
    assert new_config.system_prompt == "Published version two"


@pytest.mark.asyncio
async def test_worker_rejects_tampered_snapshot_and_claim_mismatch() -> None:
    ctx, tenant_id, agent_id = await _seed_context()
    status, body = await _mint(ctx, tenant_id, agent_id, "tamper-plan")
    assert status == 200
    payload = verify_session_jwt(str(body["token"]))
    session = await ctx.session_repo.get_session(tenant_id, str(body["session_id"]))
    assert session is not None
    session.runtime_plan_snapshot["system_prompt"] = "tampered"

    with pytest.raises(SessionPlanLoadError, match="hash"):
        await _load_session_config(payload, mint_context=ctx)


@pytest.mark.asyncio
async def test_invalid_selection_and_unpublished_agent_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx, tenant_id, agent_id = await _seed_context()
    status, body = await _mint(ctx, tenant_id, agent_id, "bad-language", language="fr")
    assert status == 422
    assert body["code"] == "SESSION_SELECTION_INVALID"

    other_tenant = str(uuid4())
    other_agent = str(uuid4())
    empty_ctx = MintContext(agent_config_repo=AgentConfigRepo())
    await empty_ctx.tenant_repo.create_tenant(Tenant(id=other_tenant, name="Empty"))
    await empty_ctx.tenant_repo.save_agent(
        Agent(id=other_agent, tenant_id=other_tenant, name="Unpublished")
    )
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.setenv("UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES", "1")

    class AllowRateLimit:
        def is_allowed(self, _tenant_id: str) -> bool:
            return True

    class AvailableReplayStore:
        async def set(
            self, _key: str, _value: str, *, ex: int, nx: bool = False
        ) -> bool:
            return ex > 0 and nx

    empty_ctx.rate_limiter = AllowRateLimit()  # type: ignore[assignment]
    empty_ctx.nonce_store = NonceStore(redis_client=AvailableReplayStore())
    status, body = await _mint(
        empty_ctx, other_tenant, other_agent, "unpublished-production"
    )
    assert status == 409
    assert body["code"] == "PUBLISHED_CONFIG_REQUIRED"


@pytest.mark.asyncio
async def test_second_worker_context_loads_pinned_snapshot_without_compiler_repo() -> (
    None
):
    ctx, tenant_id, agent_id = await _seed_context()
    status, body = await _mint(ctx, tenant_id, agent_id, "shared-session-store")
    assert status == 200
    payload = verify_session_jwt(str(body["token"]))

    worker_ctx = MintContext(
        tenant_repo=ctx.tenant_repo,
        session_repo=ctx.session_repo,
        agent_config_repo=AgentConfigRepo(),
    )
    config = await _load_session_config(payload, mint_context=worker_ctx)

    assert config.system_prompt == "Published clinic assistant"
    assert config.session_plan_hash == payload["session_plan_hash"]


class _RecordingTransport:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    async def send_control_event(
        self, event_type: str, payload: dict[str, object]
    ) -> None:
        self.events.append((event_type, payload))


@pytest.mark.asyncio
async def test_published_prompt_cannot_be_changed_by_session_messages() -> None:
    transport = _RecordingTransport()
    runner = object.__new__(WebSocketSessionRunner)
    runner.transport = transport
    runner.config = PipelineSessionConfig(
        session_id="session",
        tenant_id="tenant",
        agent_id="agent",
        system_prompt="published prompt",
        plan_authoritative=True,
        allow_unsafe_session_overrides=False,
    )

    applied = await runner._apply_system_prompt_override("attacker prompt")

    assert applied is False
    assert runner.config.system_prompt == "published prompt"
    assert transport.events[-1][1]["code"] == "SESSION_OVERRIDE_FORBIDDEN"


@pytest.mark.asyncio
async def test_explicit_local_unsafe_mode_can_change_session_prompt() -> None:
    transport = _RecordingTransport()
    runner = object.__new__(WebSocketSessionRunner)
    runner.transport = transport
    runner.config = PipelineSessionConfig(
        session_id="session",
        tenant_id="tenant",
        agent_id="agent",
        system_prompt="published prompt",
        allow_unsafe_session_overrides=True,
    )

    applied = await runner._apply_system_prompt_override("local test prompt")

    assert applied is True
    assert runner.config.system_prompt == "local test prompt"


def test_language_router_is_constrained_to_published_languages() -> None:
    router = LanguageRouter()
    router.set_supported_languages(("en", "ur"))

    assert (
        router.route({"text": "bonjour tout le monde", "language": "fr"}, "en") == "en"
    )
    assert router.route({"text": "aap kaisay hain", "language": "ur"}, "en") == "ur"


@pytest.mark.asyncio
async def test_tool_handler_rejects_tools_outside_published_allowlist() -> None:
    handler = PipelineToolHandler()
    handler.set_allowed_tools(("book_appointment",))

    result = await handler.handle_tool_call("delete_account", {})

    assert result["is_error"] is True
    assert "not enabled" in str(result["content"])
