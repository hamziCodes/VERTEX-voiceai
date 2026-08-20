"""UCVE Provider Registry & Failover Exceptions."""

from __future__ import annotations


class ConfigurationError(Exception):
    """Raised when provider registry or priority chain configuration is invalid."""


class NoProviderAvailableError(Exception):
    """Raised when all providers in a priority chain have failed or are unavailable."""


class ProviderTimeoutError(Exception):
    """Raised when a provider call times out."""


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is requested on an OPEN circuit breaker."""
