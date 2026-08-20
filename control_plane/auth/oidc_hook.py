"""UCVE OIDC Provider Protocol & Adapter Hook Interface."""

from __future__ import annotations

from typing import Any, Protocol


class OIDCProvider(Protocol):
    """Protocol for enterprise SSO OIDC auth provider integrations (Auth0/Okta/Keycloak)."""

    def authenticate_token(self, token: str) -> dict[str, Any]:
        """Authenticate ID token and return user profile claims."""
        ...


class OIDCProviderStub:
    """Default stub implementation for OIDC provider hook."""

    def authenticate_token(self, token: str) -> dict[str, Any]:
        if not token:
            raise ValueError("OIDC token required.")
        return {
            "sub": "oidc-user-stub",
            "email": "admin@example.com",
            "iss": "https://auth.example.com",
        }
