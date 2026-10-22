"""UCVE OIDC Provider Protocol & Adapter Hook Interface."""

from __future__ import annotations

from typing import Any, Protocol

from core.runtime.env import is_protected_environment


class OIDCNotConfigured(RuntimeError):
    """Raised when OIDC is required but no real provider is registered."""


class OIDCProvider(Protocol):
    """Protocol for enterprise SSO OIDC auth provider integrations (Auth0/Okta/Keycloak)."""

    def authenticate_token(self, token: str) -> dict[str, Any]:
        """Authenticate ID token and return user profile claims."""
        ...


class OIDCProviderStub:
    """Non-production stub. Must not be the default authenticator in production."""

    def authenticate_token(self, token: str) -> dict[str, Any]:
        if is_protected_environment():
            raise OIDCNotConfigured(
                "OIDC stub is disabled when UCVE_ENV=production; register a real provider."
            )
        if not token:
            raise ValueError("OIDC token required.")
        return {
            "sub": "oidc-user-stub",
            "email": "admin@example.com",
            "iss": "https://auth.example.com",
        }


_registered_provider: OIDCProvider | None = None


def register_oidc_provider(provider: OIDCProvider) -> None:
    """Register the active OIDC provider (replaces stub for production)."""
    global _registered_provider
    _registered_provider = provider


def get_oidc_provider() -> OIDCProvider:
    if _registered_provider is not None:
        return _registered_provider
    if is_protected_environment():
        raise OIDCNotConfigured(
            "No OIDC provider registered; refuse stub default in production."
        )
    return OIDCProviderStub()


def authenticate_token(token: str) -> dict[str, Any]:
    """Authenticate via registered provider, or stub outside production."""
    return get_oidc_provider().authenticate_token(token)
