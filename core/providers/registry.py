"""UCVE Provider Registry, Validation, & Failover Export Layer."""

from __future__ import annotations

from typing import Any

from core.providers.circuit_breaker import CircuitBreakerConfig, CircuitState
from core.providers.exceptions import ConfigurationError, NoProviderAvailableError
from core.providers.failover import FailoverRouter, ProviderHealthState
from core.providers.spec import ProviderCategory, ProviderSpec, get_provider_spec


class ProviderRegistry:
    """Registered adapter classes backed by strict provider specifications."""

    _registered_providers: dict[str, type[Any]] = {}

    @classmethod
    def register_provider_class(cls, provider_id: str, provider_cls: type[Any]) -> None:
        """Register a concrete provider adapter class."""
        spec = get_provider_spec(provider_id)
        cls._registered_providers[spec.provider_id] = provider_cls

    @classmethod
    def get_provider_class(cls, provider_id: str) -> type[Any] | None:
        """Retrieve registered provider class by ID."""
        return cls._registered_providers.get(provider_id.strip().lower())

    @staticmethod
    def get_provider_spec(
        provider_id: str,
        *,
        category: ProviderCategory | None = None,
        language: str | None = None,
    ) -> ProviderSpec:
        """Return the immutable capability contract for a provider."""

        return get_provider_spec(
            provider_id,
            category=category,
            language=language,
        )

    @classmethod
    def validate_chain(
        cls,
        category: str,
        language: str,
        priority: list[str],
    ) -> bool:
        """Validate resilience count and every provider capability."""
        if len(priority) < 2:
            raise ConfigurationError(
                f"Priority chain for {category!r}/{language!r} requires at least "
                f"2 enabled providers; got {len(priority)}."
            )
        try:
            requested_category = ProviderCategory(category.strip().lower())
        except ValueError as exc:
            raise ConfigurationError(
                f"Unknown provider category: {category!r}"
            ) from exc
        for provider_id in priority:
            get_provider_spec(
                provider_id,
                category=requested_category,
                language=language,
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
