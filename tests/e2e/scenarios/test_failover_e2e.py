from __future__ import annotations

import pytest
from core.providers.circuit_breaker import CircuitBreakerConfig, CircuitState
from core.providers.failover import ProviderHealthState


def test_provider_failover_circuit_breaker() -> None:
    config = CircuitBreakerConfig(failure_threshold=3, cooldown_seconds=10.0)
    health = ProviderHealthState(provider_id="mock_stt", rolling_window_size=5)

    assert health.circuit_state == CircuitState.CLOSED
    assert health.should_allow_request(config) is True

    # Record 3 failures
    health.record_failure(config)
    health.record_failure(config)
    health.record_failure(config)

    # Circuit should now be open, rejecting calls
    assert health.circuit_state == CircuitState.OPEN
    assert health.should_allow_request(config) is False

