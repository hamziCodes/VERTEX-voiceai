from __future__ import annotations

import asyncio
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from control_plane.auth.context import AuthContext
from core.db.repos.post_call_repo import InMemoryPostCallRepository
from post_call.jobs.models import PostCallIntelligenceResult
from post_call.jobs.repository import InMemoryPostCallJobRepository
from post_call.review.models import ReviewDecision
from post_call.review.repository import InMemoryReviewRepository
from post_call.webhook.dispatcher import (
    VaultWebhookSecretResolver,
    WebhookDispatcher,
)
from post_call.webhook.models import TenantWebhookTarget, WebhookDeliveryState
from post_call.webhook.policy import WebhookEndpointPolicy
from post_call.webhook.repository import (
    InMemoryWebhookRepository,
    WebhookReviewRequiredError,
)
from post_call.webhook.service import WebhookDeliveryWorker, WebhookTargetManager


def _auth(tenant_id: str) -> AuthContext:
    return AuthContext(
        subject_id="operator-1",
        tenant_id=tenant_id,
        roles=("tenant_admin",),
        scopes=frozenset({"webhook:write", "extraction:write"}),
        auth_method="oidc",
    )


async def _approved_setup() -> tuple[
    InMemoryWebhookRepository,
    PostCallIntelligenceResult,
    TenantWebhookTarget,
]:
    calls = InMemoryPostCallRepository()
    reviews = InMemoryReviewRepository(calls._post_call_reviews)
    intelligence = InMemoryPostCallJobRepository(calls)
    repo = InMemoryWebhookRepository(
        review_repository=reviews,
        intelligence_repository=intelligence,
    )
    tenant_id, call_id = uuid4(), uuid4()
    result = PostCallIntelligenceResult(
        tenant_id=tenant_id,
        call_id=call_id,
        extraction={"fields": {"lead_status": {"value": "qualified"}}},
    )
    calls._post_call_results[(tenant_id, call_id)] = result
    review = await reviews.create_pending(
        tenant_id=tenant_id,
        call_id=call_id,
        result_id=result.result_id,
        reasons=("external_action_policy",),
    )
    await reviews.decide(
        tenant_id=tenant_id,
        review_id=review.review_id,
        decision=ReviewDecision.APPROVE,
        auth=_auth(str(tenant_id)),
        note="Approved for CRM delivery.",
    )
    manager = WebhookTargetManager(
        repository=repo,
        endpoint_policy=WebhookEndpointPolicy(
            resolver=lambda _host: ("93.184.216.34",)
        ),
    )
    target = await manager.create_and_approve(
        tenant_id=tenant_id,
        name="Primary CRM",
        url="https://crm.example.test/events",
        credential_ref="crm-signing-v1",
        auth=_auth(str(tenant_id)),
    )
    return repo, result, target


@pytest.mark.asyncio
async def test_enqueue_requires_approved_review_and_is_logically_idempotent() -> None:
    calls = InMemoryPostCallRepository()
    reviews = InMemoryReviewRepository(calls._post_call_reviews)
    intelligence = InMemoryPostCallJobRepository(calls)
    repo = InMemoryWebhookRepository(
        review_repository=reviews,
        intelligence_repository=intelligence,
    )
    tenant_id, call_id = uuid4(), uuid4()
    result = PostCallIntelligenceResult(tenant_id=tenant_id, call_id=call_id)
    calls._post_call_results[(tenant_id, call_id)] = result
    review = await reviews.create_pending(
        tenant_id=tenant_id,
        call_id=call_id,
        result_id=result.result_id,
        reasons=("external_action_policy",),
    )
    manager = WebhookTargetManager(
        repository=repo,
        endpoint_policy=WebhookEndpointPolicy(
            resolver=lambda _host: ("93.184.216.34",)
        ),
    )
    target = await manager.create_and_approve(
        tenant_id=tenant_id,
        name="CRM",
        url="https://crm.example.test/events",
        credential_ref="crm-signing-v1",
        auth=_auth(str(tenant_id)),
    )
    with pytest.raises(WebhookReviewRequiredError):
        await repo.enqueue_delivery(
            tenant_id=tenant_id,
            target_id=target.target_id,
            call_id=call_id,
            result_id=result.result_id,
            review_id=review.review_id,
            event_type="post_call.intelligence.completed",
        )

    await reviews.decide(
        tenant_id=tenant_id,
        review_id=review.review_id,
        decision=ReviewDecision.APPROVE,
        auth=_auth(str(tenant_id)),
        note="Approved.",
    )
    first = await repo.enqueue_delivery(
        tenant_id=tenant_id,
        target_id=target.target_id,
        call_id=call_id,
        result_id=result.result_id,
        review_id=review.review_id,
        event_type="post_call.intelligence.completed",
    )
    duplicate = await repo.enqueue_delivery(
        tenant_id=tenant_id,
        target_id=target.target_id,
        call_id=call_id,
        result_id=result.result_id,
        review_id=review.review_id,
        event_type="post_call.intelligence.completed",
    )

    assert duplicate.delivery_id == first.delivery_id
    assert duplicate.idempotency_key == first.idempotency_key
    assert first.payload == {
        "schema_version": "wavia.post_call.intelligence.v1",
        "call_id": str(call_id),
        "result_id": str(result.result_id),
        "extraction": None,
        "summary": None,
        "verification_issue_codes": [],
    }


@pytest.mark.asyncio
async def test_worker_persists_retry_then_success_without_duplicate_delivery() -> None:
    repo, result, target = await _approved_setup()
    review = await repo.review_repository.get_for_result(
        result.tenant_id, result.result_id
    )
    assert review is not None
    delivery = await repo.enqueue_delivery(
        tenant_id=result.tenant_id,
        target_id=target.target_id,
        call_id=result.call_id,
        result_id=result.result_id,
        review_id=review.review_id,
        event_type="post_call.intelligence.completed",
        now=datetime(2026, 10, 26, 12, 0, tzinfo=UTC),
    )
    requests: list[httpx.Request] = []
    statuses = iter((503, 204))

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(next(statuses), request=request, text="not persisted")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def resolve_secret(_tenant_id: str, credential_ref: str) -> str:
        assert credential_ref == "crm-signing-v1"
        return "test-signing-secret"

    dispatcher = WebhookDispatcher(
        secret_resolver=resolve_secret,
        client=client,
        endpoint_policy=WebhookEndpointPolicy(
            resolver=lambda _host: ("93.184.216.34",)
        ),
    )
    worker = WebhookDeliveryWorker(
        repository=repo,
        dispatcher=dispatcher,
        worker_id="delivery-worker-1",
    )

    assert await worker.run_once(now=delivery.available_at) is True
    waiting = await repo.get_delivery(result.tenant_id, delivery.delivery_id)
    assert waiting.state is WebhookDeliveryState.RETRY_WAIT
    assert await worker.run_once(now=waiting.available_at) is True
    succeeded = await repo.get_delivery(result.tenant_id, delivery.delivery_id)
    attempts = await repo.list_attempts(result.tenant_id, delivery.delivery_id)

    assert succeeded.state is WebhookDeliveryState.SUCCEEDED
    assert len(attempts) == 2
    assert attempts[0].status_code == 503
    assert attempts[0].error_code == "remote_unavailable"
    assert attempts[1].status_code == 204
    assert attempts[1].error_code is None
    assert all(attempt.response_body is None for attempt in attempts)
    assert len(requests) == 2
    assert requests[0].headers["X-Idempotency-Key"] == delivery.idempotency_key
    assert requests[1].headers["X-Idempotency-Key"] == delivery.idempotency_key
    expected_body = WebhookDispatcher.canonical_payload(delivery.payload)
    expected_signature = hmac.new(
        b"test-signing-secret", expected_body, hashlib.sha256
    ).hexdigest()
    assert requests[0].content == expected_body
    assert requests[0].headers["X-Wavia-Signature"] == expected_signature
    assert await worker.run_once(now=waiting.available_at + timedelta(days=1)) is False
    await client.aclose()


@pytest.mark.asyncio
async def test_redirect_is_terminal_and_response_body_is_never_stored() -> None:
    repo, result, target = await _approved_setup()
    review = await repo.review_repository.get_for_result(
        result.tenant_id, result.result_id
    )
    assert review is not None
    delivery = await repo.enqueue_delivery(
        tenant_id=result.tenant_id,
        target_id=target.target_id,
        call_id=result.call_id,
        result_id=result.result_id,
        review_id=review.review_id,
        event_type="post_call.intelligence.completed",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"Location": "http://127.0.0.1/private"},
            request=request,
            text="sensitive vendor response",
        )

    async def resolve_secret(_tenant_id: str, _credential_ref: str) -> str:
        return "test-signing-secret"

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    worker = WebhookDeliveryWorker(
        repository=repo,
        dispatcher=WebhookDispatcher(
            secret_resolver=resolve_secret,
            client=client,
            endpoint_policy=WebhookEndpointPolicy(
                resolver=lambda _host: ("93.184.216.34",)
            ),
        ),
        worker_id="delivery-worker-1",
    )

    assert await worker.run_once(now=delivery.available_at) is True
    failed = await repo.get_delivery(result.tenant_id, delivery.delivery_id)
    attempts = await repo.list_attempts(result.tenant_id, delivery.delivery_id)
    assert failed.state is WebhookDeliveryState.DEAD_LETTER
    assert attempts[0].error_code == "redirect_blocked"
    assert attempts[0].response_body is None
    await client.aclose()


@pytest.mark.asyncio
async def test_missing_credential_and_total_timeout_fail_safely() -> None:
    repo, result, target = await _approved_setup()
    review = await repo.review_repository.get_for_result(
        result.tenant_id, result.result_id
    )
    assert review is not None
    delivery = await repo.enqueue_delivery(
        tenant_id=result.tenant_id,
        target_id=target.target_id,
        call_id=result.call_id,
        result_id=result.result_id,
        review_id=review.review_id,
        event_type="post_call.intelligence.completed",
    )
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return httpx.Response(204, request=request)

    async def missing_secret(_tenant_id: str, _credential_ref: str) -> str:
        raise LookupError("not found")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    missing = await WebhookDispatcher(
        secret_resolver=missing_secret,
        client=client,
        endpoint_policy=WebhookEndpointPolicy(
            resolver=lambda _host: ("93.184.216.34",)
        ),
    ).send_once(target, delivery)
    assert missing.error_code == "credential_unavailable"
    assert missing.retryable is False
    assert calls == 0

    async def present_secret(_tenant_id: str, _credential_ref: str) -> str:
        return "test-signing-secret"

    timed_out = await WebhookDispatcher(
        secret_resolver=present_secret,
        client=client,
        endpoint_policy=WebhookEndpointPolicy(
            resolver=lambda _host: ("93.184.216.34",)
        ),
        total_timeout_seconds=0.01,
    ).send_once(target, delivery)
    assert timed_out.error_code == "delivery_timeout"
    assert timed_out.retryable is True
    assert calls == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_vault_resolver_requests_tenant_byok_hmac_reference() -> None:
    calls: list[tuple[str, str, str, str, str]] = []

    class _Resolved:
        secret = "resolved-test-secret"

    class _Vault:
        async def aresolve_credential(
            self,
            tenant_id: str,
            provider_id: str,
            *,
            credential_ref: str,
            credential_type: str,
            tier: str,
        ) -> _Resolved:
            calls.append(
                (
                    tenant_id,
                    provider_id,
                    credential_ref,
                    credential_type,
                    tier,
                )
            )
            return _Resolved()

    secret = await VaultWebhookSecretResolver(_Vault())("tenant-1", "crm-signing")

    assert secret == "resolved-test-secret"
    assert calls == [("tenant-1", "webhook", "crm-signing", "hmac_secret", "byok")]


@pytest.mark.asyncio
async def test_oversized_payload_is_terminal_before_network_io() -> None:
    repo, result, target = await _approved_setup()
    review = await repo.review_repository.get_for_result(
        result.tenant_id, result.result_id
    )
    assert review is not None
    result.extraction = {"large": "x" * 2_000}
    repo.intelligence_repository._results[(result.tenant_id, result.call_id)] = result
    delivery = await repo.enqueue_delivery(
        tenant_id=result.tenant_id,
        target_id=target.target_id,
        call_id=result.call_id,
        result_id=result.result_id,
        review_id=review.review_id,
        event_type="post_call.intelligence.completed",
    )
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(204, request=request)

    async def resolve_secret(_tenant_id: str, _credential_ref: str) -> str:
        return "test-signing-secret"

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    attempt = await WebhookDispatcher(
        secret_resolver=resolve_secret,
        client=client,
        endpoint_policy=WebhookEndpointPolicy(
            resolver=lambda _host: ("93.184.216.34",)
        ),
        max_payload_bytes=1_024,
    ).send_once(target, delivery)

    assert attempt.error_code == "payload_too_large"
    assert attempt.retryable is False
    assert calls == 0
    await client.aclose()
