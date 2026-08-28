"""R0 harness gate tests — scenario dispatch + failure injection."""

from __future__ import annotations

import pytest

from tests.e2e.harness import E2EHarness, HarnessConfig, ScenarioResult, list_scenarios


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)


def test_harness_returns_false_on_injected_failure(test_env: None) -> None:
    harness = E2EHarness(
        HarnessConfig(
            scenario="sovereign_conversation",
            extra={"inject_failure": True},
        )
    )
    assert harness.run() is False
    result = harness.run_scenario("sovereign_conversation")
    assert isinstance(result, ScenarioResult)
    assert result.passed is False
    assert result.failures


@pytest.mark.asyncio
async def test_sovereign_conversation_scenario_passes(test_env: None) -> None:
    harness = E2EHarness(HarnessConfig(scenario="sovereign_conversation"))
    result = await harness.run_scenario_async("sovereign_conversation")
    assert result.passed, result.failures
    assert result.metrics.get("post_call_enqueued", 0) >= 1


def test_scenario_registry_lists_sovereign(test_env: None) -> None:
    names = list_scenarios()
    assert "sovereign_conversation" in names


@pytest.mark.asyncio
async def test_scenario_force_fail_via_extra(test_env: None) -> None:
    harness = E2EHarness(
        HarnessConfig(
            scenario="sovereign_conversation",
            extra={"scenario_force_fail": True},
        )
    )
    result = await harness.run_scenario_async("sovereign_conversation")
    assert result.passed is False
    assert any("forced" in f for f in result.failures)
