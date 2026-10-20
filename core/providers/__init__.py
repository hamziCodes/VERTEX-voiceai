"""UCVE Provider Interfaces & Adapters Core Package."""

from __future__ import annotations

from core.providers import adapters, interfaces
from core.providers.circuit_breaker import CircuitBreakerConfig, CircuitState
from core.providers.config_schema import AgentProviderConfig, ProviderChainConfig
from core.providers.exceptions import (
    CircuitBreakerOpenError,
    ConfigurationError,
    NoProviderAvailableError,
    ProviderCapabilityError,
    ProviderFailure,
    ProviderFailureCategory,
    ProviderTimeoutError,
    UnknownProviderError,
    classify_http_failure,
)
from core.providers.failover import FailoverRouter, ProviderHealthState
from core.providers.registry import ProviderRegistry
from core.providers.spec import (
    ADVERTISED_PROVIDER_IDS,
    CredentialPolicyState,
    ProviderCategory,
    ProviderRolloutState,
    ProviderSpec,
    get_provider_spec,
)

__all__ = [
    "interfaces",
    "adapters",
    "ProviderRegistry",
    "FailoverRouter",
    "ProviderHealthState",
    "CircuitBreakerConfig",
    "CircuitState",
    "AgentProviderConfig",
    "ProviderChainConfig",
    "ConfigurationError",
    "ProviderCapabilityError",
    "ProviderFailure",
    "ProviderFailureCategory",
    "UnknownProviderError",
    "classify_http_failure",
    "ADVERTISED_PROVIDER_IDS",
    "CredentialPolicyState",
    "ProviderCategory",
    "ProviderRolloutState",
    "ProviderSpec",
    "get_provider_spec",
    "NoProviderAvailableError",
    "ProviderTimeoutError",
    "CircuitBreakerOpenError",
]
