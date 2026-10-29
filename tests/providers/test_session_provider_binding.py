"""Published session plans bind complete provider chains before readiness."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.providers.exceptions import (
    NoProviderAvailableError,
    ProviderFailure,
    ProviderFailureCategory,
    ProviderInvocationError,
)
from core.providers.routing import ProviderRouteIdentity, ResolvedProviderRoute
from core.runtime.session_plan import RuntimeProviderRoute
from core.secrets.exceptions import SecretNotFoundError
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.provider_binding import ProviderSessionBinder
from worker_raw.orchestration.session_config import PipelineSessionConfig


@dataclass
class _Adapter:
    name: str
    close_calls: int = 0

    async def aclose(self) -> None:
        self.close_calls += 1


class _Builder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.adapters: list[_Adapter] = []

    def build_chain(self, tenant_id, category, language, routes):
        if self.fail:
            raise SecretNotFoundError("credential unavailable")
        result = []
        for route in routes:
            adapter = _Adapter(f"{category}:{route.provider_id}")
            self.adapters.append(adapter)
            result.append(
                ResolvedProviderRoute(
                    identity=ProviderRouteIdentity(
                        category=str(category),
                        provider_id=route.provider_id,
                        model=route.model,
                        region="provider_managed",
                        tenant_id=tenant_id,
                        credential_scope=f"scope-{tenant_id}-{route.provider_id}",
                    ),
                    adapter=adapter,
                )
            )
        return tuple(result)


def _config() -> PipelineSessionConfig:
    def routes(first: str, second: str) -> list[dict[str, object]]:
        return [
            RuntimeProviderRoute(provider_id=first, priority=1).model_dump(mode="json"),
            RuntimeProviderRoute(provider_id=second, priority=2).model_dump(
                mode="json"
            ),
        ]

    return PipelineSessionConfig(
        session_id="session",
        tenant_id="tenant-a",
        agent_id="agent",
        plan_authoritative=True,
        allowed_languages=("en",),
        provider_chain={
            "stt": routes("gladia", "deepgram"),
            "llm": routes("groq", "gemini"),
            "tts": routes("cartesia", "elevenlabs"),
        },
    )


@pytest.mark.asyncio
async def test_binder_constructs_all_six_routes_before_returning() -> None:
    builder = _Builder()
    bound = await ProviderSessionBinder(builder).bind(_config())

    assert len(bound.stt) == len(bound.llm) == len(bound.tts) == 2
    assert len({id(route.adapter) for route in bound.all_routes}) == 6
    assert len(builder.adapters) == 6


@pytest.mark.asyncio
async def test_unavailable_credential_rejects_authoritative_startup() -> None:
    orchestrator = PipelineOrchestrator(
        provider_binder=ProviderSessionBinder(_Builder(fail=True))
    )

    with pytest.raises(SecretNotFoundError, match="credential unavailable"):
        await orchestrator.apply_provider_selection(_config())

    assert orchestrator.bound_provider_chains is None


@pytest.mark.asyncio
async def test_orchestrator_uses_independent_bound_routers() -> None:
    orchestrator = PipelineOrchestrator(
        provider_binder=ProviderSessionBinder(_Builder())
    )
    await orchestrator.apply_provider_selection(_config())

    assert orchestrator.bound_provider_chains is not None
    bound = orchestrator.bound_provider_chains
    assert orchestrator.stt_provider is bound.stt[0].adapter
    assert orchestrator.llm_provider is bound.llm[0].adapter
    assert orchestrator.tts_provider is bound.tts[0].adapter
    assert orchestrator.llm_router.priority == list(bound.llm)

    calls: list[str] = []

    async def invoke(route: ResolvedProviderRoute) -> str:
        calls.append(route.adapter.name)
        if route.identity.provider_id == "groq":
            raise ProviderInvocationError(
                ProviderFailure(
                    provider_id="groq",
                    category=ProviderFailureCategory.TRANSIENT_SERVER,
                    retryable=True,
                )
            )
        return route.adapter.name

    selected = await orchestrator.llm_router.call_with_failover("llm", "en", invoke)
    assert selected == "llm:gemini"
    assert calls == ["llm:groq", "llm:gemini"]


@pytest.mark.asyncio
async def test_bound_teardown_closes_every_adapter_exactly_once() -> None:
    builder = _Builder()
    bound = await ProviderSessionBinder(builder).bind(_config())

    await bound.aclose()
    await bound.aclose()

    assert [adapter.close_calls for adapter in builder.adapters] == [1] * 6


def test_production_disallows_synthetic_llm_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "0")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")

    assert PipelineOrchestrator._synthetic_provider_reply_allowed() is False
    assert issubclass(NoProviderAvailableError, Exception)
