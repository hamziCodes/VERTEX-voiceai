"""UCVE Control-Plane Auth & Security Package."""

from __future__ import annotations

from control_plane.auth import api_keys, hmac_mint, jwt, middleware, oidc_hook, rate_limit, rbac
from control_plane.auth.api_keys import APIKeyManager
from control_plane.auth.hmac_mint import NonceStore, expected_signature, verify_mint_signature
from control_plane.auth.jwt import issue_session_jwt, verify_session_jwt
from control_plane.auth.middleware import enforce_rbac
from control_plane.auth.oidc_hook import (
    OIDCNotConfigured,
    OIDCProvider,
    OIDCProviderStub,
    authenticate_token,
    get_oidc_provider,
    register_oidc_provider,
)
from control_plane.auth.rate_limit import RateLimiter
from control_plane.auth.rbac import RBACManager

__all__ = [
    "api_keys",
    "hmac_mint",
    "jwt",
    "middleware",
    "oidc_hook",
    "rate_limit",
    "rbac",
    "expected_signature",
    "verify_mint_signature",
    "NonceStore",
    "issue_session_jwt",
    "verify_session_jwt",
    "APIKeyManager",
    "RBACManager",
    "RateLimiter",
    "OIDCProvider",
    "OIDCProviderStub",
    "OIDCNotConfigured",
    "authenticate_token",
    "get_oidc_provider",
    "register_oidc_provider",
    "enforce_rbac",
]
