"""Auditable authentication classification for control-plane HTTP surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AuthClass = Literal["public", "management", "session", "carrier", "operations"]


@dataclass(frozen=True, slots=True)
class RoutePolicy:
    method: str
    path_prefix: str
    auth_class: AuthClass
    permission: str | None = None
    exact: bool = True


ROUTE_POLICIES: tuple[RoutePolicy, ...] = (
    RoutePolicy("GET", "/", "public"),
    RoutePolicy("GET", "/health", "public"),
    RoutePolicy("GET", "/health/live", "public"),
    RoutePolicy("GET", "/health/ready", "public"),
    RoutePolicy("GET", "/favicon.ico", "public"),
    RoutePolicy("GET", "/json/version", "public"),
    RoutePolicy("GET", "/demo", "public", exact=False),
    RoutePolicy("GET", "/docs", "public", exact=False),
    RoutePolicy("GET", "/redoc", "public"),
    RoutePolicy("GET", "/openapi.json", "public"),
    RoutePolicy("POST", "/v1/session", "session"),
    RoutePolicy("POST", "/v1/session/mint", "session"),
    RoutePolicy("POST", "/mint", "session"),
    RoutePolicy("POST", "/v1/session/refresh", "session"),
    RoutePolicy(
        "POST", "/v1/studio/sessions", "management", "session:mint"
    ),
    RoutePolicy(
        "POST", "/v1/telephony/calls", "management", "telephony:write"
    ),
    RoutePolicy("GET", "/v1/me", "management", "identity:read"),
    RoutePolicy("POST", "/v1/organizations", "management", "workspace:write"),
    RoutePolicy(
        "GET",
        "/v1/organizations/{tenant_id}/members",
        "management",
        "member:read",
    ),
    RoutePolicy(
        "POST",
        "/v1/organizations/{tenant_id}/invitations",
        "management",
        "member:write",
    ),
    RoutePolicy(
        "PATCH",
        "/v1/organizations/{tenant_id}/members/{user_id}",
        "management",
        "member:write",
    ),
    RoutePolicy(
        "DELETE",
        "/v1/organizations/{tenant_id}/members/{user_id}",
        "management",
        "member:write",
    ),
    RoutePolicy(
        "POST", "/v1/invitations/accept", "management", "invitation:accept"
    ),
    RoutePolicy("GET", "/v1/onboarding", "management", "onboarding:read"),
    RoutePolicy("PATCH", "/v1/onboarding", "management", "onboarding:write"),
    RoutePolicy("GET", "/v1/entitlements", "management", "entitlement:read"),
    RoutePolicy("GET", "/v1/catalog/providers", "management", "agent:read"),
    RoutePolicy("GET", "/v1/agents/templates", "management", "agent:read"),
    RoutePolicy(
        "GET", "/v1/conversations", "management", "conversation:read", exact=False
    ),
    RoutePolicy(
        "GET", "/v1/telephony/settings", "management", "telephony:read"
    ),
    RoutePolicy(
        "PUT", "/v1/telephony/settings", "management", "telephony:write"
    ),
    RoutePolicy("GET", "/v1/api-keys", "management", "api_key:read", exact=False),
    RoutePolicy("POST", "/v1/api-keys", "management", "api_key:write"),
    RoutePolicy(
        "DELETE", "/v1/api-keys/{key_id}", "management", "api_key:write"
    ),
    RoutePolicy(
        "GET",
        "/v1/provider-credentials",
        "management",
        "provider_credential:read",
        exact=False,
    ),
    RoutePolicy(
        "POST",
        "/v1/provider-credentials",
        "management",
        "provider_credential:write",
    ),
    RoutePolicy(
        "DELETE",
        "/v1/provider-credentials/{credential_id}",
        "management",
        "provider_credential:write",
    ),
    RoutePolicy("GET", "/metrics", "operations"),
    RoutePolicy("POST", "/v1/agents", "management", "agent:write"),
    RoutePolicy("GET", "/v1/agents", "management", "agent:read"),
    RoutePolicy("GET", "/v1/agents/{agent_id}", "management", "agent:read"),
    RoutePolicy("PATCH", "/v1/agents/{agent_id}/autosave", "management", "agent:write"),
    RoutePolicy("POST", "/v1/agents/{agent_id}/publish", "management", "agent:write"),
    RoutePolicy("POST", "/v1/agents/{agent_id}/validate", "management", "agent:read"),
    RoutePolicy(
        "POST",
        "/v1/agents/{agent_id}/versions/{version}/restore",
        "management",
        "agent:write",
    ),
    RoutePolicy("GET", "/v1/agents/{agent_id}/versions", "management", "agent:read"),
    RoutePolicy(
        "GET",
        "/v1/agents/{agent_id}/versions/{version}",
        "management",
        "agent:read",
    ),
    RoutePolicy("POST", "/v1/agents/{agent_id}/pin", "management", "agent:write"),
    RoutePolicy(
        "GET", "/v1/knowledge-bases", "management", "knowledge:read", exact=False
    ),
    RoutePolicy(
        "POST", "/v1/knowledge-bases", "management", "knowledge:write", exact=False
    ),
    RoutePolicy(
        "POST",
        "/v1/extraction-schemas",
        "management",
        "extraction:write",
    ),
    RoutePolicy("GET", "/v1/alerts/{tenant_id}", "management", "alert:read"),
    RoutePolicy(
        "POST",
        "/v1/conversations/{call_id}/legal-hold",
        "management",
        "legal_hold:manage",
    ),
    RoutePolicy(
        "POST",
        "/v1/conversations/{call_id}/deletion",
        "management",
        "erasure:execute",
    ),
    RoutePolicy("POST", "/v1/workspace/erasure", "management", "erasure:execute"),
    RoutePolicy("GET", "/v1/privacy-jobs/{job_id}", "management", "erasure:execute"),
    RoutePolicy("GET", "/v1/webhook-targets", "management", "webhook:read"),
    RoutePolicy("POST", "/v1/webhook-targets", "management", "webhook:write"),
    RoutePolicy(
        "POST", "/v1/webhook-targets/{target_id}/disable", "management", "webhook:write"
    ),
    RoutePolicy(
        "POST", "/v1/conversations/{call_id}/review", "management", "extraction:write"
    ),
    RoutePolicy("GET", "/v1/usage", "management", "usage:read"),
    RoutePolicy("GET", "/v1/audit", "management", "audit:read"),
    RoutePolicy("POST", "/v1/secrets/rotate", "management", "secret:rotate"),
)
