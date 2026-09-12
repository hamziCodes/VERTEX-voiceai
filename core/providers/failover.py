"""UCVE Provider Failover Router & Health State Tracking."""

from __future__ import annotations

import asyncio
from collections import deque
import time
from typing import Any, Awaitable, Callable, TypeVar

from core.providers.circuit_breaker import CircuitBreakerConfig, CircuitState
from core.providers.exceptions import NoProviderAvailableError

T = TypeVar("T")


class ProviderHealthState:
    """Runtime health state & circuit breaker metrics per provider instance."""

    def __init__(self, provider_id: str, rolling_window_size: int = 10) -> None:
        self.provider_id = provider_id
        self.circuit_state: CircuitState = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.recent_results: deque[bool] = deque(maxlen=rolling_window_size)
        self.last_failure_timestamp: float = 0.0
        self.last_latency_ms: float = 0.0
        self.priority_index: int = 0

    def should_allow_request(self, config: CircuitBreakerConfig, now_ts: float | None = None) -> bool:
        """Return True if request should be allowed through circuit breaker."""
        now = time.time() if now_ts is None else now_ts
        if self.circuit_state == CircuitState.CLOSED:
            return True
        if self.circuit_state == CircuitState.OPEN:
            if now - self.last_failure_timestamp >= config.cooldown_seconds:
                self.circuit_state = CircuitState.HALF_OPEN
                return True
            return False
        if self.circuit_state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self, latency_ms: float = 0.0) -> None:
        """Record successful invocation and reset failure metrics."""
        self.consecutive_failures = 0
        self.recent_results.append(True)
        self.last_latency_ms = latency_ms
        self.circuit_state = CircuitState.CLOSED

    def record_failure(self, config: CircuitBreakerConfig, now_ts: float | None = None) -> None:
        """Record failed invocation and re-evaluate circuit state."""
        now = time.time() if now_ts is None else now_ts
        self.consecutive_failures += 1
        self.recent_results.append(False)
        self.last_failure_timestamp = now
        self.update_circuit_state(config)

    def update_circuit_state(self, config: CircuitBreakerConfig) -> None:
        """Evaluate failure thresholds and trip circuit to OPEN if exceeded."""
        error_count = sum(1 for res in self.recent_results if not res)
        total_count = len(self.recent_results)
        error_rate = (error_count / total_count) if total_count > 0 else 0.0

        if (
            self.consecutive_failures >= config.failure_threshold
            or (total_count >= 5 and error_rate >= config.error_rate_threshold)
        ):
            self.circuit_state = CircuitState.OPEN


class FailoverRouter:
    """Runtime router attempting priority chain invocation with circuit breaker failover."""

    def __init__(
        self,
        priority: list[str] | None = None,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self.priority = list(priority or ["primary", "secondary"])
        self.config = config or CircuitBreakerConfig()
        self.health_map: dict[str, ProviderHealthState] = {
            pid: ProviderHealthState(pid, rolling_window_size=self.config.rolling_window_size)
            for pid in self.priority
        }

    async def call_with_failover(
        self,
        category: str,
        language: str,
        invoke_fn: Callable[[str], Awaitable[T]],
        first_chunk_timeout: float = 15.0,
        subsequent_chunk_timeout: float = 5.0,
    ) -> T:
        """Execute call against priority chain with automatic failover on error/circuit-open."""
        errors: list[tuple[str, Exception]] = []
        now_ts = time.time()

        for provider_id in self.priority:
            health = self.health_map.setdefault(
                provider_id,
                ProviderHealthState(provider_id, rolling_window_size=self.config.rolling_window_size),
            )

            if not health.should_allow_request(self.config, now_ts=now_ts):
                continue

            start_time = time.perf_counter()
            try:
                # Wrap invocation with timeout
                result = await asyncio.wait_for(invoke_fn(provider_id), timeout=first_chunk_timeout)
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                health.record_success(latency_ms=latency_ms)
                return result
            except Exception as exc:
                health.record_failure(self.config, now_ts=time.time())
                errors.append((provider_id, exc))

        err_msg = f"All providers in priority chain for {category}/{language} failed or are unavailable: {self.priority}. Errors: {errors}"
        raise NoProviderAvailableError(err_msg)
