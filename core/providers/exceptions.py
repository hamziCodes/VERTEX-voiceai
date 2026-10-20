"""UCVE Provider Registry & Failover Exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ConfigurationError(Exception):
    """Raised when provider registry or priority chain configuration is invalid."""


class UnknownProviderError(ConfigurationError):
    """Raised when a provider ID is absent from the source-controlled catalog."""


class ProviderCapabilityError(ConfigurationError):
    """Raised when a provider cannot satisfy a requested runtime capability."""


class ProviderFailureCategory(StrEnum):
    """Stable failure categories used by routing and observability."""

    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CONFIGURATION = "configuration"
    INVALID_REQUEST = "invalid_request"
    INVALID_OUTPUT = "invalid_output"
    TRANSIENT_SERVER = "transient_server"
    PERMANENT = "permanent"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    """Sanitized provider failure metadata; never contains response bodies."""

    provider_id: str
    category: ProviderFailureCategory
    retryable: bool
    status_code: int | None = None


def classify_http_failure(provider_id: str, status_code: int) -> ProviderFailure:
    """Map an HTTP status to one deterministic, provider-neutral failure."""

    if status_code in {401, 403}:
        category = ProviderFailureCategory.AUTHENTICATION
        retryable = False
    elif status_code == 402:
        category = ProviderFailureCategory.QUOTA
        retryable = False
    elif status_code == 408:
        category = ProviderFailureCategory.TIMEOUT
        retryable = True
    elif status_code == 429:
        category = ProviderFailureCategory.RATE_LIMIT
        retryable = True
    elif 500 <= status_code <= 599:
        category = ProviderFailureCategory.TRANSIENT_SERVER
        retryable = True
    elif status_code in {400, 404, 405, 409, 415, 422}:
        category = ProviderFailureCategory.INVALID_REQUEST
        retryable = False
    else:
        category = ProviderFailureCategory.PERMANENT
        retryable = False
    return ProviderFailure(
        provider_id=provider_id.strip().lower(),
        category=category,
        retryable=retryable,
        status_code=status_code,
    )


class NoProviderAvailableError(Exception):
    """Raised when all providers in a priority chain have failed or are unavailable."""


class ProviderTimeoutError(Exception):
    """Raised when a provider call times out."""


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is requested on an OPEN circuit breaker."""
