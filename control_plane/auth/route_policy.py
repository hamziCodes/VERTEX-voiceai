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
        "POST", "/v1/telephony/calls", "management", "telephony:write"
    ),
    RoutePolicy("GET", "/metrics", "operations"),
    RoutePolicy("POST", "/v1/agents", "management", "agent:write"),
    RoutePolicy("GET", "/v1/agents", "management", "agent:read"),
    RoutePolicy("GET", "/v1/agents/{agent_id}", "management", "agent:read"),
    RoutePolicy("PATCH", "/v1/agents/{agent_id}/autosave", "management", "agent:write"),
    RoutePolicy("POST", "/v1/agents/{agent_id}/publish", "management", "agent:write"),
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
    RoutePolicy(
        "POST",
        "/v1/alerts/config/{tenant_id}",
        "management",
        "alert:write",
    ),
    RoutePolicy("GET", "/v1/usage", "management", "usage:read"),
    RoutePolicy("GET", "/v1/audit", "management", "audit:read"),
    RoutePolicy("POST", "/v1/secrets/rotate", "management", "secret:rotate"),
)
