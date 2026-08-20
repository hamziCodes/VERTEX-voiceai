"""UCVE Provider Registry, Validation, & Failover Export Layer."""

from __future__ import annotations

from typing import Any, Type

from core.providers.circuit_breaker import CircuitBreakerConfig, CircuitState
from core.providers.exceptions import ConfigurationError, NoProviderAvailableError
from core.providers.failover import FailoverRouter, ProviderHealthState


class ProviderRegistry:
    """Registry maintaining registered provider classes and validating resilience rules."""

    _registered_providers: dict[str, Type[Any]] = {}

    @classmethod
    def register_provider_class(cls, provider_id: str, provider_cls: Type[Any]) -> None:
        """Register a concrete provider adapter class."""
        cls._registered_providers[provider_id] = provider_cls

    @classmethod
    def get_provider_class(cls, provider_id: str) -> Type[Any] | None:
        """Retrieve registered provider class by ID."""
        return cls._registered_providers.get(provider_id)

    @classmethod
    def validate_chain(
        cls, category: str, language: str, priority: list[str]
    ) -> bool:
        """Validate priority chain resilience requirement (minimum 2 providers per category/language)."""
        if len(priority) < 2:
            raise ConfigurationError(
                f"Priority chain for category '{category}' and language '{language}' must have at least 2 enabled providers for resilience. Got {len(priority)}."
            )
        return True


__all__ = [
    "ProviderRegistry",
    "FailoverRouter",
    "ProviderHealthState",
    "CircuitBreakerConfig",
    "CircuitState",
    "ConfigurationError",
    "NoProviderAvailableError",
]

