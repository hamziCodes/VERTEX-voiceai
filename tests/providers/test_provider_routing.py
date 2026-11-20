"""Independent provider routes and scoped circuit-breaker contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from core.listening.config import SpeakingPipelineConfig
from core.providers.circuit_breaker import CircuitBreakerConfig, CircuitState
from core.providers.exceptions import (
    ConfigurationError,
    NoProviderAvailableError,
    ProviderFailure,
    ProviderFailureCategory,
    ProviderInvocationError,
    UnknownProviderError,
    provider_invocation_error,
)
from core.providers.failover import FailoverRouter, ProviderHealthState
from core.providers.routing import ProviderRouteBuilder
from core.runtime.session_plan import RuntimeProviderRoute
from core.secrets.policy import CredentialTier, ResolvedCredential


class _Resolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def resolve_credential(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        credential_ref: str | None,
        credential_type: str,
        tier: CredentialTier,
    ) -> ResolvedCredential:
        self.calls.append((tenant_id, provider_id))
        return ResolvedCredential(
            tenant_id=tenant_id,
            provider_id=provider_id,
            credential_type=credential_type,
            requested_tier=tier,
            source_tier=CredentialTier.PLATFORM,
            credential_ref=credential_ref,
            rotation_version="test-v1",
            secret=f"injected-{provider_id}",
        )


def _routes() -> tuple[RuntimeProviderRoute, ...]:
    return (
        RuntimeProviderRoute(
            provider_id="groq",
            model="openai/gpt-oss-120b",
            priority=1,
            credential_tier=CredentialTier.PLATFORM,
        ),
        RuntimeProviderRoute(
            provider_id="gemini",
            model="gemini-2.5-flash",
            priority=2,
            credential_tier=CredentialTier.PLATFORM,
        ),
    )


def test_route_builder_constructs_distinct_adapters_with_route_identity() -> None:
    resolver = _Resolver()
    chain = ProviderRouteBuilder(resolver).build_chain(
        "tenant-a", "llm", "ur", _routes()
    )

    assert [route.identity.provider_id for route in chain] == ["groq", "gemini"]
    assert chain[0].adapter is not chain[1].adapter
    assert chain[0].adapter.api_key == "injected-groq"
    assert chain[1].adapter.api_key == "injected-gemini"
    assert chain[0].identity.credential_scope != chain[1].identity.credential_scope


def test_route_builder_preserves_pipeline_tuning_for_bound_adapters() -> None:
    speaking = SpeakingPipelineConfig(
        enabled_phases=frozenset({"speaking_hardening"}),
        tts_chunk_size_bytes=777,
    )
    builder = ProviderRouteBuilder(
        _Resolver(),
        speaking_config=speaking,
        stt_mock_text="offline transcript",
    )
    stt = builder.build_chain(
        "tenant-a",
        "stt",
        "en",
        (
            RuntimeProviderRoute(provider_id="gladia", priority=1),
            RuntimeProviderRoute(provider_id="deepgram", priority=2),
        ),
    )
    tts = builder.build_chain(
        "tenant-a",
        "tts",
        "en",
        (
            RuntimeProviderRoute(provider_id="cartesia", priority=1),
            RuntimeProviderRoute(provider_id="elevenlabs", priority=2),
        ),
    )

    assert stt[0].adapter.mock_text == "offline transcript"
    assert stt[1].adapter.mock_text == "offline transcript"
    assert tts[0].adapter.chunk_size_bytes == 777
    assert tts[1].adapter.chunk_size_bytes == 777


def test_catalog_validation_precedes_credential_resolution() -> None:
    resolver = _Resolver()
    invalid = _routes()[0].model_copy(update={"provider_id": "unknown"})

    with pytest.raises(UnknownProviderError):
        ProviderRouteBuilder(resolver).build_chain(
            "tenant-a", "llm", "en", (invalid, _routes()[1])
        )

    assert resolver.calls == []


def test_builder_requires_two_usable_routes() -> None:
    with pytest.raises(ConfigurationError, match="at least two"):
        ProviderRouteBuilder(_Resolver()).build_chain(
            "tenant-a", "llm", "en", (_routes()[0],)
        )


def test_credential_failures_are_isolated_by_tenant_scope() -> None:
    builder = ProviderRouteBuilder(_Resolver())
    tenant_a = builder.build_chain("tenant-a", "llm", "en", _routes())[0]
    tenant_b = builder.build_chain("tenant-b", "llm", "en", _routes())[0]
    router = FailoverRouter(
        priority=[tenant_a, tenant_b],
        config=CircuitBreakerConfig(),
    )

    router.record_route_failure(
        tenant_a,
        ProviderFailure(
            provider_id="groq",
            category=ProviderFailureCategory.AUTHENTICATION,
            retryable=False,
        ),
    )

    assert router.is_route_available(tenant_a) is False
    assert router.is_route_available(tenant_b) is True


def test_transient_failures_share_provider_scope_but_not_category() -> None:
    builder = ProviderRouteBuilder(_Resolver())
    llm_a = builder.build_chain("tenant-a", "llm", "en", _routes())[0]
    llm_b = builder.build_chain("tenant-b", "llm", "en", _routes())[0]
    stt_groq = replace(llm_b, identity=replace(llm_b.identity, category="stt"))
    router = FailoverRouter(
        priority=[llm_a, llm_b, stt_groq],
        config=CircuitBreakerConfig(failure_threshold=1),
    )

    router.record_route_failure(
        llm_a,
        ProviderFailure(
            provider_id="groq",
            category=ProviderFailureCategory.TRANSIENT_SERVER,
            retryable=True,
        ),
    )

    assert router.is_route_available(llm_b) is False
    assert router.is_route_available(stt_groq) is True


def test_half_open_allows_exactly_one_probe() -> None:
    health = ProviderHealthState("route", rolling_window_size=2)
    config = CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=1)
    health.record_failure(config, now_ts=10)

    assert health.should_allow_request(config, now_ts=11) is True
    assert health.circuit_state is CircuitState.HALF_OPEN
    assert health.should_allow_request(config, now_ts=11) is False
    health.record_success()
    assert health.should_allow_request(config, now_ts=11) is True


def test_partial_route_admission_releases_earlier_half_open_probe() -> None:
    route = ProviderRouteBuilder(_Resolver()).build_chain(
        "tenant-a", "llm", "en", _routes()
    )[0]
    config = CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=1)
    router = FailoverRouter(priority=[route], config=config)
    credential_key, provider_key = router._scope_keys(route)
    credential_health = router._health(credential_key)
    provider_health = router._health(provider_key)
    credential_health.record_failure(config, now_ts=10)
    provider_health.record_failure(config, now_ts=20)

    assert router.is_route_available(route, now_ts=11) is False
    assert credential_health.circuit_state is CircuitState.HALF_OPEN
    assert credential_health._half_open_probe_in_flight is False


@pytest.mark.asyncio
async def test_aggregate_error_contains_sanitized_route_evidence() -> None:
    chain = ProviderRouteBuilder(_Resolver()).build_chain(
        "tenant-a", "llm", "en", _routes()
    )
    router = FailoverRouter(priority=list(chain))

    async def fail(route):
        raise ProviderInvocationError(
            ProviderFailure(
                provider_id=route.identity.provider_id,
                category=ProviderFailureCategory.AUTHENTICATION,
                retryable=False,
                status_code=401,
            )
        )

    with pytest.raises(NoProviderAvailableError) as exc_info:
        await router.call_with_failover("llm", "en", fail)

    message = str(exc_info.value)
    assert "authentication" in message
    assert "groq" in message and "gemini" in message
    assert "ProviderInvocationError" not in message


def test_adapter_exception_mapping_is_typed_and_omits_exception_text() -> None:
    mapped = provider_invocation_error(
        "groq", RuntimeError("sensitive upstream response")
    )

    assert mapped.failure.category is ProviderFailureCategory.TRANSIENT_SERVER
    assert "sensitive upstream response" not in str(mapped)
