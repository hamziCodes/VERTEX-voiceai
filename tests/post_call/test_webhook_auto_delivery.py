"""Stage 3: webhooks deliver automatically unless the review policy flagged the call."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from control_plane.auth.context import AuthContext
from core.db.repos.post_call_repo import InMemoryPostCallRepository
from post_call.jobs.models import PostCallIntelligenceResult
from post_call.jobs.repository import InMemoryPostCallJobRepository
from post_call.review.models import ReviewDecision
from post_call.review.repository import InMemoryReviewRepository
from post_call.webhook.fanout import enqueue_for_result
from post_call.webhook.policy import WebhookEndpointPolicy
from post_call.webhook.repository import InMemoryWebhookRepository, WebhookReviewRequiredError
from post_call.webhook.service import WebhookTargetManager

PUBLIC = WebhookEndpointPolicy(resolver=lambda _host: ("93.184.216.34",))


def _auth(tenant_id: str) -> AuthContext:
    # Exactly what a signed-in Studio admin presents: OIDC sessions carry no
    # scopes, so the role must be enough (Stage 3 found the repositories
    # refusing every signed-in member).
    return AuthContext(
        subject_id="operator-1",
        tenant_id=tenant_id,
        roles=("tenant_admin",),
        scopes=frozenset(),
        auth_method="oidc",
    )


async def _setup(*, flagged: bool):
    calls = InMemoryPostCallRepository()
    reviews = InMemoryReviewRepository(calls._post_call_reviews)
    repo = InMemoryWebhookRepository(
        review_repository=reviews, intelligence_repository=InMemoryPostCallJobRepository(calls)
    )
    tenant_id, call_id = uuid4(), uuid4()
    result = PostCallIntelligenceResult(tenant_id=tenant_id, call_id=call_id, summary={"executive_summary": "x"})
    calls._post_call_results[(tenant_id, call_id)] = result
    review = None
    if flagged:
        review = await reviews.create_pending(
            tenant_id=tenant_id, call_id=call_id, result_id=result.result_id, reasons=("sensitive_field",)
        )
    manager = WebhookTargetManager(repository=repo, endpoint_policy=PUBLIC)
    for name in ("CRM", "Warehouse"):
        await manager.create_and_approve(
            tenant_id=tenant_id, name=name, url=f"https://{name.lower()}.example.test/hook",
            credential_ref=f"{name.lower()}-ref", auth=_auth(str(tenant_id)),
        )
    return repo, reviews, result, review


@pytest.mark.asyncio
async def test_unflagged_result_delivers_to_every_active_target() -> None:
    repo, _reviews, result, _ = await _setup(flagged=False)
    targets = await repo.list_targets(result.tenant_id)
    await repo.disable_target(tenant_id=result.tenant_id, target_id=targets[1].target_id, auth=_auth(str(result.tenant_id)))

    count = await enqueue_for_result(repo, tenant_id=result.tenant_id, call_id=result.call_id, result_id=result.result_id)

    assert count == 1
    deliveries = list(repo._deliveries.values())
    assert [d.target_id for d in deliveries] == [targets[0].target_id]
    assert deliveries[0].review_id is None
    # Idempotent: a repeat does not create a second delivery.
    await enqueue_for_result(repo, tenant_id=result.tenant_id, call_id=result.call_id, result_id=result.result_id)
    assert len(repo._deliveries) == 1


@pytest.mark.asyncio
async def test_flagged_result_waits_for_approval() -> None:
    repo, reviews, result, review = await _setup(flagged=True)
    assert review is not None

    held = await enqueue_for_result(repo, tenant_id=result.tenant_id, call_id=result.call_id, result_id=result.result_id)
    assert held == 0
    with pytest.raises(WebhookReviewRequiredError):
        target = (await repo.list_targets(result.tenant_id))[0]
        await repo.enqueue_delivery(
            tenant_id=result.tenant_id, target_id=target.target_id, call_id=result.call_id,
            result_id=result.result_id, event_type="post_call.intelligence.completed",
        )

    await reviews.decide(
        tenant_id=result.tenant_id, review_id=review.review_id, decision=ReviewDecision.APPROVE,
        auth=_auth(str(result.tenant_id)), note="ok",
    )
    approved = await enqueue_for_result(
        repo, tenant_id=result.tenant_id, call_id=result.call_id,
        result_id=result.result_id, review_id=review.review_id,
    )
    assert approved == 2


def test_target_api_reveals_the_secret_once_and_review_api_decides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_DEMO_MODE", "0")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    with TestClient(app) as client:
        app.state.webhook_endpoint_policy = PUBLIC
        tenant = str(uuid4())
        raw, _ = app.state.api_keys.generate_api_key(
            tenant, "hooks", scopes=["webhook:read", "webhook:write", "extraction:write"], role="tenant_admin"
        )
        headers = {"Authorization": f"Bearer {raw}", "X-Tenant-Id": tenant}

        rejected = client.post("/v1/webhook-targets", headers=headers, json={"name": "Local", "url": "http://10.0.0.5/hook"})
        created = client.post("/v1/webhook-targets", headers=headers, json={"name": "CRM", "url": "https://crm.example.test/hook"})
        listed = client.get("/v1/webhook-targets", headers=headers)
        target_id = created.json()["target_id"]
        disabled = client.post(f"/v1/webhook-targets/{target_id}/disable", headers=headers)
        no_result = client.post(f"/v1/conversations/{uuid4()}/review", headers=headers, json={"decision": "approve"})

    assert rejected.status_code == 422
    assert created.status_code == 201, created.text
    assert created.json()["signing_secret"].startswith("whsec_")
    assert created.json()["state"] == "active"
    assert listed.status_code == 200
    assert "signing_secret" not in listed.json()[0]
    assert disabled.json()["state"] == "disabled"
    assert no_result.status_code == 404
