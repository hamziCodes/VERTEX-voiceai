"""UCVE Provider Failover Router & Health State Tracking."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from core.providers.circuit_breaker import CircuitBreakerConfig, CircuitState
from core.providers.exceptions import (
    NoProviderAvailableError,
    ProviderFailure,
    ProviderFailureCategory,
    ProviderInvocationError,
)

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
        self._half_open_probe_in_flight = False

    def should_allow_request(
        self, config: CircuitBreakerConfig, now_ts: float | None = None
    ) -> bool:
        """Return True if request should be allowed through circuit breaker."""
        now = time.time() if now_ts is None else now_ts
        if self.circuit_state == CircuitState.CLOSED:
            return True
        if self.circuit_state == CircuitState.OPEN:
            if now - self.last_failure_timestamp >= config.cooldown_seconds:
                self.circuit_state = CircuitState.HALF_OPEN
                self._half_open_probe_in_flight = True
                return True
            return False
        if self.circuit_state == CircuitState.HALF_OPEN:
            if self._half_open_probe_in_flight:
                return False
            self._half_open_probe_in_flight = True
            return True
        return False

    def record_success(self, latency_ms: float = 0.0) -> None:
        """Record successful invocation and reset failure metrics."""
        self.consecutive_failures = 0
        self.recent_results.append(True)
        self.last_latency_ms = latency_ms
        self.circuit_state = CircuitState.CLOSED
        self._half_open_probe_in_flight = False

    def record_failure(
        self, config: CircuitBreakerConfig, now_ts: float | None = None
    ) -> None:
        """Record failed invocation and re-evaluate circuit state."""
        now = time.time() if now_ts is None else now_ts
        self.consecutive_failures += 1
        self.recent_results.append(False)
        self.last_failure_timestamp = now
        self._half_open_probe_in_flight = False
        self.update_circuit_state(config)

    def release_probe(self) -> None:
        """Release a half-open lease when an invocation is cancelled."""
        self._half_open_probe_in_flight = False

    def update_circuit_state(self, config: CircuitBreakerConfig) -> None:
        """Evaluate failure thresholds and trip circuit to OPEN if exceeded."""
        error_count = sum(1 for res in self.recent_results if not res)
        total_count = len(self.recent_results)
        error_rate = (error_count / total_count) if total_count > 0 else 0.0

        if self.consecutive_failures >= config.failure_threshold or (
            total_count >= 5 and error_rate >= config.error_rate_threshold
        ):
            self.circuit_state = CircuitState.OPEN


class FailoverRouter:
    """Runtime router attempting priority chain invocation with circuit breaker failover."""

    def __init__(
        self,
        priority: list[Any] | None = None,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self.priority = list(priority or ["primary", "secondary"])
        self.config = config or CircuitBreakerConfig()
        self.health_map: dict[Any, ProviderHealthState] = {
            pid: ProviderHealthState(
                pid, rolling_window_size=self.config.rolling_window_size
            )
            for pid in self.priority
            if isinstance(pid, str)
        }
        self._scoped_health: dict[Any, ProviderHealthState] = {}

    @staticmethod
    def _identity(route: Any) -> Any | None:
        return getattr(route, "identity", None)

    def _scope_keys(self, route: Any) -> tuple[Any, Any]:
        identity = self._identity(route)
        if identity is None:
            return route, route
        return identity.credential_health_key, identity.provider_health_key

    def _health(self, key: Any) -> ProviderHealthState:
        if isinstance(key, str):
            return self.health_map.setdefault(
                key,
                ProviderHealthState(
                    key, rolling_window_size=self.config.rolling_window_size
                ),
            )
        return self._scoped_health.setdefault(
            key,
            ProviderHealthState(
                str(key), rolling_window_size=self.config.rolling_window_size
            ),
        )

    def is_route_available(self, route: Any, *, now_ts: float | None = None) -> bool:
        credential_key, provider_key = self._scope_keys(route)
        keys = (
            (credential_key,)
            if credential_key == provider_key
            else (
                credential_key,
                provider_key,
            )
        )
        acquired_probes: list[ProviderHealthState] = []
        for key in keys:
            health = self._health(key)
            if not health.should_allow_request(self.config, now_ts=now_ts):
                for acquired in acquired_probes:
                    acquired.release_probe()
                return False
            if health.circuit_state is CircuitState.HALF_OPEN:
                acquired_probes.append(health)
        return True

    def record_route_failure(
        self,
        route: Any,
        failure: ProviderFailure,
        *,
        now_ts: float | None = None,
    ) -> None:
        credential_key, provider_key = self._scope_keys(route)
        credential_categories = {
            ProviderFailureCategory.AUTHENTICATION,
            ProviderFailureCategory.QUOTA,
            ProviderFailureCategory.RATE_LIMIT,
            ProviderFailureCategory.CONFIGURATION,
            ProviderFailureCategory.INVALID_REQUEST,
        }
        key = (
            credential_key
            if failure.category in credential_categories
            else provider_key
        )
        health = self._health(key)
        health.record_failure(self.config, now_ts=now_ts)
        if not failure.retryable:
            health.circuit_state = CircuitState.OPEN

    def _record_success(self, route: Any, latency_ms: float) -> None:
        credential_key, provider_key = self._scope_keys(route)
        for key in {credential_key, provider_key}:
            self._health(key).record_success(latency_ms=latency_ms)

    def _release_probes(self, route: Any) -> None:
        credential_key, provider_key = self._scope_keys(route)
        for key in {credential_key, provider_key}:
            self._health(key).release_probe()

    async def call_with_failover(
        self,
        category: str,
        language: str,
        invoke_fn: Callable[[Any], Awaitable[T]],
        first_chunk_timeout: float = 15.0,
        subsequent_chunk_timeout: float = 5.0,
    ) -> T:
        """Execute call against priority chain with automatic failover on error/circuit-open."""
        errors: list[tuple[str, ProviderFailureCategory]] = []
        now_ts = time.time()

        for route in self.priority:
            if not self.is_route_available(route, now_ts=now_ts):
                continue

            start_time = time.perf_counter()
            try:
                # Wrap invocation with timeout
                result = await asyncio.wait_for(
                    invoke_fn(route), timeout=first_chunk_timeout
                )
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                self._record_success(route, latency_ms)
                return result
            except asyncio.CancelledError:
                self._release_probes(route)
                raise
            except ProviderInvocationError as exc:
                self.record_route_failure(route, exc.failure, now_ts=time.time())
                self._release_probes(route)
                errors.append((exc.failure.provider_id, exc.failure.category))
            except TimeoutError:
                identity = self._identity(route)
                provider_id = getattr(identity, "provider_id", str(route))
                failure = ProviderFailure(
                    provider_id=provider_id,
                    category=ProviderFailureCategory.TIMEOUT,
                    retryable=True,
                )
                self.record_route_failure(route, failure, now_ts=time.time())
                self._release_probes(route)
                errors.append((provider_id, failure.category))
            except Exception:
                identity = self._identity(route)
                provider_id = getattr(identity, "provider_id", str(route))
                failure = ProviderFailure(
                    provider_id=provider_id,
                    category=ProviderFailureCategory.PERMANENT,
                    retryable=False,
                )
                self.record_route_failure(route, failure, now_ts=time.time())
                self._release_probes(route)
                errors.append((provider_id, failure.category))

        evidence = ", ".join(
            f"{provider}:{failure.value}" for provider, failure in errors
        )
        err_msg = (
            f"All providers for {category}/{language} failed or are unavailable. "
            f"Failures: {evidence or 'circuits_open'}"
        )
        raise NoProviderAvailableError(err_msg)
