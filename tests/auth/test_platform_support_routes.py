"""Phase 13K: support-session API, safe projections and operations health."""

from __future__ import annotations

import asyncio
from inspect import isawaitable
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from control_plane.studio.repository import InMemoryStudioRepository

REASON = "Customer ticket about agent setup"
SECRET_MARKERS = (
    "SECRET-PROMPT-TEXT",
    "SECRET-GREETING",
    "secret_lookup_tool",
    "mcp.secret.example",
    "+15550001111",
    "system_prompt",
    "greeting",
    "tools",
    "mcp_servers",
    "persona",
)


class _Claims:
    def authenticate_token(self, token: str) -> dict[str, object]:
        name = token.removesuffix("-token")
        if name == token:
            raise KeyError(token)
        return {
            "sub": name,
            "iss": "https://identity.test",
            "email": f"{name}@wavia.test",
        }


def _auth(name: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {name}-token", **extra}


async def _resolve(value: Any) -> Any:
    return await value if isawaitable(value) else value


@pytest.fixture
def support_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    monkeypatch.setenv("RUN_LIVE_TELEPHONY", "0")
    from control_plane.agents.models.agent_config import AgentConfig
    from control_plane.app import app
    from control_plane.routes.agents import get_agent_repo
    from core.db.repos.knowledge_repo import get_default_knowledge_repository

    repository = InMemoryStudioRepository()
    with TestClient(app) as client:
        app.state.oidc_provider = _Claims()
        app.state.studio_repository = repository
        ids: dict[str, UUID] = {}
        for name in ("admin", "support", "other", "customer"):
            response = client.get("/v1/me", headers=_auth(name))
            assert response.status_code == 200, response.text
            ids[name] = UUID(response.json()["user_id"])
        asyncio.run(
            repository.bootstrap_platform_admin(
                ids["admin"], reason="Initial operator bootstrap"
            )
        )
        for name in ("support", "other"):
            granted = client.put(
                "/v1/platform/staff",
                headers=_auth("admin"),
                json={
                    "email": f"{name}@wavia.test",
                    "role": "platform_support",
                    "reason": "Support rota for launch",
                },
            )
            assert granted.status_code == 200, granted.text
        tenant = client.post(
            "/v1/organizations", headers=_auth("customer"), json={"name": "Acme"}
        )
        assert tenant.status_code == 201
        tenant_id = UUID(tenant.json()["tenant_id"])
        ids["tenant"] = tenant_id
        agent = AgentConfig.model_validate(
            {
                "tenant_id": tenant_id,
                "name": "Front desk",
                "description": "Answers booking questions",
                "persona": {
                    "system_prompt": "SECRET-PROMPT-TEXT",
                    "greeting": "SECRET-GREETING",
                },
                "languages": ["en", "ur"],
                "tools": [{"name": "secret_lookup_tool"}],
                "mcp_servers": [{"url": "https://mcp.secret.example"}],
                "telephony": {"number": "+15550001111"},
            }
        )
        asyncio.run(_resolve(get_agent_repo().create_agent(agent)))
        asyncio.run(
            _resolve(
                get_default_knowledge_repository().create_knowledge_base(
                    tenant_id, "Booking FAQ"
                )
            )
        )
        yield client, repository, ids
    for name in ("oidc_provider", "studio_repository"):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _start(client: TestClient, tenant: UUID, actor: str = "support", **body: Any):
    payload = {
        "reason": REASON,
        "reference": "TICKET-1042",
        "scopes": ["configuration"],
        "duration_minutes": 30,
    }
    payload.update(body)
    return client.post(
        f"/v1/platform/tenants/{tenant}/support-sessions",
        headers=_auth(actor),
        json=payload,
    )


def _routes(tenant: UUID, session: UUID) -> list[tuple[str, str]]:
    return [
        ("POST", f"/v1/platform/tenants/{tenant}/support-sessions"),
        ("GET", "/v1/platform/support-sessions"),
        ("GET", f"/v1/platform/support-sessions/{session}"),
        ("POST", f"/v1/platform/support-sessions/{session}/end"),
        ("GET", f"/v1/platform/support-sessions/{session}/configuration"),
        ("GET", f"/v1/platform/support-sessions/{session}/readiness"),
        ("GET", "/v1/platform/operations"),
    ]


def test_new_platform_routes_reject_non_staff_and_tenant_context(support_api) -> None:
    client, _, ids = support_api
    session = UUID(_start(client, ids["tenant"]).json()["session_id"])
    api_key = {"Authorization": "Bearer ucve_live_not-a-staff-credential"}
    for method, path in _routes(ids["tenant"], session):
        assert client.request(method, path, json={}).status_code == 401, path
        assert client.request(method, path, headers=api_key, json={}).status_code == 401
        tenant_header = _auth("admin", **{"X-Tenant-Id": str(ids["tenant"])})
        assert (
            client.request(method, path, headers=tenant_header, json={}).status_code
            == 400
        ), path
        customer = client.request(method, path, headers=_auth("customer"), json={})
        assert customer.status_code == 403, path


def test_every_platform_route_requires_platform_authentication(support_api) -> None:
    client, _, _ = support_api
    from control_plane.app import app

    # Included routers are nested in this FastAPI version; OpenAPI lists them all.
    checked = 0
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith("/v1/platform"):
            continue
        concrete = path
        while "{" in concrete:
            start = concrete.index("{")
            end = concrete.index("}", start)
            concrete = concrete[:start] + str(uuid4()) + concrete[end + 1 :]
        for method in operations:
            response = client.request(method.upper(), concrete, json={})
            assert response.status_code == 401, (method, path)
            checked += 1
    assert checked >= 13


def test_start_validates_and_prevents_duplicates(support_api) -> None:
    client, _, ids = support_api
    assert _start(client, ids["tenant"], duration_minutes=90).status_code == 422
    assert _start(client, ids["tenant"], reason="short").status_code == 422
    assert _start(client, ids["tenant"], scopes=["transcripts"]).status_code == 422
    assert _start(client, ids["tenant"], scopes=[]).status_code == 422
    assert _start(client, uuid4()).status_code == 404
    started = _start(client, ids["tenant"], scopes=["readiness", "configuration"])
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["state"] == "active"
    assert body["scopes"] == ["configuration", "readiness"]
    assert body["tenant_name"] == "Acme"
    assert body["actor_email"] == "support@wavia.test"
    assert _start(client, ids["tenant"]).status_code == 409


def test_configuration_projection_is_an_allowlist_and_audited(support_api) -> None:
    client, _, ids = support_api
    session = _start(client, ids["tenant"]).json()["session_id"]
    response = client.get(
        f"/v1/platform/support-sessions/{session}/configuration",
        headers=_auth("support"),
    )
    assert response.status_code == 200, response.text
    for marker in SECRET_MARKERS:
        assert marker not in response.text, marker
    body = response.json()
    assert set(body) == {"session", "agents", "knowledge_bases"}
    assert body["session"]["session_id"] == session
    agent = body["agents"][0]
    assert set(agent) == {
        "agent_id",
        "name",
        "description",
        "languages",
        "version",
        "draft_revision",
        "is_published",
        "published_at",
        "provider_route_counts",
        "knowledge_base_count",
        "tool_count",
        "mcp_server_count",
        "telephony_configured",
        "compliance_tier",
    }
    assert agent["name"] == "Front desk"
    assert agent["tool_count"] == 1
    assert agent["mcp_server_count"] == 1
    assert agent["telephony_configured"] is True
    assert set(agent["provider_route_counts"]) == {"stt", "llm", "tts", "s2s"}
    assert body["knowledge_bases"][0]["name"] == "Booking FAQ"
    assert set(body["knowledge_bases"][0]) == {
        "knowledge_base_id",
        "name",
        "status",
        "source_count",
        "ready_source_count",
        "updated_at",
    }

    audit = client.get("/v1/platform/audit", headers=_auth("admin")).json()
    viewed = [
        item for item in audit if item["action"] == "platform_support.data_viewed"
    ]
    assert len(viewed) == 1
    assert viewed[0]["scope"] == "configuration"
    assert viewed[0]["support_session_id"] == session
    assert viewed[0]["actor_user_id"] == str(ids["support"])


def test_readiness_projection_and_scope_owner_and_state_checks(support_api) -> None:
    client, _, ids = support_api
    session = _start(client, ids["tenant"], scopes=["readiness"]).json()["session_id"]
    readiness = client.get(
        f"/v1/platform/support-sessions/{session}/readiness", headers=_auth("support")
    )
    assert readiness.status_code == 200, readiness.text
    body = readiness.json()
    assert set(body) == {"session", "onboarding", "entitlements", "telephony"}
    assert body["onboarding"]["completed_steps"] == []
    assert body["entitlements"]["max_agents"] >= 1
    assert body["telephony"] == {
        "trunk_configured": False,
        "telephony_entitled": False,
        "carrier_health": "not_measured",
    }

    configuration = f"/v1/platform/support-sessions/{session}/configuration"
    assert client.get(configuration, headers=_auth("support")).status_code == 403
    readiness_path = f"/v1/platform/support-sessions/{session}/readiness"
    assert client.get(readiness_path, headers=_auth("admin")).status_code == 403
    assert client.get(readiness_path, headers=_auth("other")).status_code == 403
    unknown = f"/v1/platform/support-sessions/{uuid4()}/readiness"
    assert client.get(unknown, headers=_auth("support")).status_code == 404

    ended = client.post(
        f"/v1/platform/support-sessions/{session}/end",
        headers=_auth("support"),
        json={},
    )
    assert ended.status_code == 200
    assert ended.json()["state"] == "ended"
    assert client.get(readiness_path, headers=_auth("support")).status_code == 410


def test_ending_and_listing_respect_ownership(support_api) -> None:
    client, _, ids = support_api
    support_session = _start(client, ids["tenant"]).json()["session_id"]
    admin_session = _start(client, ids["tenant"], actor="admin").json()["session_id"]

    denied = client.post(
        f"/v1/platform/support-sessions/{admin_session}/end",
        headers=_auth("support"),
        json={},
    )
    assert denied.status_code == 403
    short = client.post(
        f"/v1/platform/support-sessions/{support_session}/end",
        headers=_auth("admin"),
        json={"reason": "no"},
    )
    assert short.status_code == 422
    managed = client.post(
        f"/v1/platform/support-sessions/{support_session}/end",
        headers=_auth("admin"),
        json={"reason": "Ending stale session after handover"},
    )
    assert managed.status_code == 200
    again = client.post(
        f"/v1/platform/support-sessions/{support_session}/end",
        headers=_auth("admin"),
        json={},
    )
    assert again.status_code == 410

    active = client.get(
        "/v1/platform/support-sessions",
        params={"state": "active"},
        headers=_auth("support"),
    )
    assert [item["session_id"] for item in active.json()] == [admin_session]
    recent = client.get("/v1/platform/support-sessions", headers=_auth("support"))
    assert {item["session_id"] for item in recent.json()} == {
        admin_session,
        support_session,
    }
    detail = client.get(
        f"/v1/platform/support-sessions/{support_session}", headers=_auth("other")
    )
    assert detail.status_code == 200
    assert detail.json()["state"] == "ended"
    bad = client.get(
        "/v1/platform/support-sessions",
        params={"state": "all", "limit": 500},
        headers=_auth("admin"),
    )
    assert bad.status_code == 422


def test_operations_snapshot_is_admin_only_and_honest(support_api) -> None:
    client, _, ids = support_api
    _start(client, ids["tenant"])
    assert (
        client.get("/v1/platform/operations", headers=_auth("support")).status_code
        == 403
    )
    response = client.get("/v1/platform/operations", headers=_auth("admin"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["environment"] == "test"
    signals = {item["key"]: item for item in body["signals"]}
    assert set(signals) == {
        "control_plane",
        "database",
        "identity",
        "post_call_queue",
        "live_providers",
        "provider_health",
        "telephony",
        "carrier_health",
        "support_sessions",
    }
    assert signals["control_plane"]["status"] == "healthy"
    assert signals["database"]["status"] == "not_configured"
    assert signals["identity"]["status"] == "healthy"
    assert signals["live_providers"]["status"] == "disabled"
    assert signals["provider_health"]["status"] == "not_measured"
    assert signals["carrier_health"]["status"] == "not_measured"
    assert signals["telephony"]["status"] == "disabled"
    assert signals["support_sessions"]["metrics"] == {"active": 1}
    assert set(signals["post_call_queue"]["metrics"]) == {
        "queued",
        "running",
        "retry_wait",
        "succeeded",
        "dead_letter",
    }
    for forbidden in ("SECRET", "password", "token", "DATABASE_URL", "postgresql://"):
        assert forbidden not in response.text
