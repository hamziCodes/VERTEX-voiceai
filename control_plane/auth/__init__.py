"""UCVE Control-Plane Auth & Security Package."""

from __future__ import annotations

from control_plane.auth import (
    api_keys,
    context,
    dependencies,
    hmac_mint,
    jwt,
    middleware,
    oidc_hook,
    rate_limit,
    rbac,
    route_policy,
)
from control_plane.auth.api_keys import APIKeyManager
from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import (
    enforce_tenant_access,
    require_permission,
    resolve_auth_context,
)
from control_plane.auth.hmac_mint import (
    NonceStore,
    expected_signature,
    verify_mint_signature,
)
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
    "context",
    "dependencies",
    "route_policy",
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
    "AuthContext",
    "resolve_auth_context",
    "require_permission",
    "enforce_tenant_access",
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
