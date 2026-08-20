"""UCVE Provider Circuit Breaker Configuration & State Enums."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Threshold & cooldown rules for provider circuit breakers."""

    failure_threshold: int = 5
    error_rate_threshold: float = 0.5
    rolling_window_size: int = 10
    cooldown_seconds: float = 30.0
