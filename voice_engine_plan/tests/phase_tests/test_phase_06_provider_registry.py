"""Phase 06: Provider Registry, Circuit Breakers, and Fallback Router."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def registry_module():
    try:
        from core.providers import registry  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 06 implementation pending: {exc}")
    return registry


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_06_provider_registry_circuit_breakers_and_fallback_router.md"
    )
    assert plan.is_file()


def test_single_provider_chain_rejected(registry_module) -> None:
    ConfigurationError = registry_module.ConfigurationError
    ProviderRegistry = registry_module.ProviderRegistry

    with pytest.raises(ConfigurationError):
        ProviderRegistry.validate_chain(category="stt", language="ur", priority=["gladia"])


@pytest.mark.asyncio
async def test_failover_uses_secondary(registry_module) -> None:
    FailoverRouter = registry_module.FailoverRouter

    calls: list[str] = []

    async def invoke(provider_id: str) -> str:
        calls.append(provider_id)
        if provider_id == "primary":
            raise RuntimeError("down")
        return "ok"

    router = FailoverRouter(priority=["primary", "secondary"])
    result = await router.call_with_failover(category="tts", language="en", invoke_fn=invoke)
    assert result == "ok"
    assert calls == ["primary", "secondary"]


def test_circuit_breaker_trips_and_recovers(registry_module) -> None:
    CircuitBreakerConfig = registry_module.CircuitBreakerConfig
    CircuitState = registry_module.CircuitState
    ProviderHealthState = registry_module.ProviderHealthState

    cfg = CircuitBreakerConfig(failure_threshold=3, cooldown_seconds=0.1)
    health = ProviderHealthState("test_provider")
    assert health.circuit_state == CircuitState.CLOSED

    # 3 consecutive failures -> trips OPEN
    for _ in range(3):
        health.record_failure(cfg)
    assert health.circuit_state == CircuitState.OPEN
    assert health.should_allow_request(cfg) is False

    # Simulate cooldown passing
    import time
    time.sleep(0.12)
    assert health.should_allow_request(cfg) is True
    assert health.circuit_state == CircuitState.HALF_OPEN

    # Record success -> resets to CLOSED
    health.record_success(latency_ms=15.0)
    assert health.circuit_state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_all_providers_failing_raises_no_provider_available(registry_module) -> None:
    FailoverRouter = registry_module.FailoverRouter
    NoProviderAvailableError = registry_module.NoProviderAvailableError

    async def always_fail(provider_id: str) -> str:
        raise RuntimeError("dead")

    router = FailoverRouter(priority=["p1", "p2"])
    with pytest.raises(NoProviderAvailableError):
        await router.call_with_failover(category="stt", language="en", invoke_fn=always_fail)

