"""E2E test: Sovereign 3-turn WebSocket conversation with mock providers (Phase 17/33)."""

from __future__ import annotations

import pytest
from tests.e2e.harness import E2EHarness, HarnessConfig


@pytest.mark.asyncio
async def test_sovereign_conversation_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    harness = E2EHarness(HarnessConfig(scenario="sovereign_conversation"))
    result = await harness.run_scenario_async("sovereign_conversation")

    assert result.passed, f"Sovereign conversation failed: {result.failures}"
    assert result.metrics.get("post_call_enqueued", 0) >= 1
