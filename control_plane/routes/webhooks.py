"""Tenant post-call webhook targets and review decisions.

Self-serve: creating a target validates the endpoint (HTTPS on 443, public
addresses only), pins the addresses it resolves to, generates a signing
secret that is stored only in the encrypted vault and shown once, and
activates the target. Deliveries are signed with HMAC-SHA256 over the raw
JSON body (``X-Wavia-Signature``) and carry ``X-Idempotency-Key``.

Results the review policy flags are held until a person approves them
(``POST /v1/conversations/{call_id}/review``); unflagged results deliver
automatically when intelligence completes.
"""

from __future__ import annotations

import secrets
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import require_permission
from post_call.review.models import ReviewDecision, ReviewState
from post_call.review.repository import (
    ReviewAuthorizationError,
    ReviewConflictError,
    ReviewNotFoundError,
)
from post_call.webhook.fanout import enqueue_for_result
from post_call.webhook.models import TenantWebhookTarget
from post_call.webhook.policy import WebhookEndpointPolicy, WebhookSecurityError
from post_call.webhook.repository import WebhookAuthorizationError, WebhookNotFoundError
from post_call.webhook.service import WebhookTargetManager

router = APIRouter(tags=["webhooks"])
WebhookReader = Annotated[AuthContext, Depends(require_permission("webhook:read"))]
WebhookWriter = Annotated[AuthContext, Depends(require_permission("webhook:write"))]
ReviewDecider = Annotated[AuthContext, Depends(require_permission("extraction:write"))]

SIGNATURE_HEADER = "X-Wavia-Signature"


class CreateWebhookTargetBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    url: str = Field(min_length=8, max_length=2_048)


class ReviewDecisionBody(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=1_000)


def _tenant(auth: AuthContext) -> UUID:
    try:
        return UUID(auth.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid tenant identifier.") from exc


def _state(request: Request, name: str) -> Any:
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(status_code=503, detail="Webhooks are unavailable.")
    return value


def _target_view(target: TenantWebhookTarget) -> dict[str, Any]:
    return {
        "target_id": str(target.target_id),
        "name": target.name,
        "url": target.url,
        "state": target.state.value,
        "created_at": target.created_at.isoformat(),
        "updated_at": target.updated_at.isoformat(),
        "signature_header": SIGNATURE_HEADER,
    }


@router.get("/v1/webhook-targets")
async def list_webhook_targets(request: Request, auth: WebhookReader) -> list[dict[str, Any]]:
    repository = _state(request, "webhook_repository")
    return [_target_view(item) for item in await repository.list_targets(_tenant(auth))]


@router.post("/v1/webhook-targets", status_code=status.HTTP_201_CREATED)
async def create_webhook_target(
    body: CreateWebhookTargetBody, request: Request, auth: WebhookWriter
) -> dict[str, Any]:
    tenant_id = _tenant(auth)
    repository = _state(request, "webhook_repository")
    vault = _state(request, "secret_vault")
    policy = getattr(request.app.state, "webhook_endpoint_policy", None) or WebhookEndpointPolicy()
    manager = WebhookTargetManager(repository=repository, endpoint_policy=policy)
    signing_secret = f"whsec_{secrets.token_urlsafe(32)}"
    credential_ref = f"webhook-{secrets.token_hex(8)}"
    try:
        # Validates HTTPS/public addresses and pins them before anything is stored.
        await policy.validate(body.url.strip())
        await vault.astore(
            str(tenant_id), "webhook", signing_secret, "hmac_secret", credential_ref=credential_ref
        )
        target = await manager.create_and_approve(
            tenant_id=tenant_id,
            name=body.name.strip(),
            url=body.url.strip(),
            credential_ref=credential_ref,
            auth=auth,
        )
    except WebhookSecurityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=422, detail="Webhook endpoint did not resolve.") from exc
    except WebhookAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {**_target_view(target), "signing_secret": signing_secret}


@router.post("/v1/webhook-targets/{target_id}/disable")
async def disable_webhook_target(
    target_id: UUID, request: Request, auth: WebhookWriter
) -> dict[str, Any]:
    repository = _state(request, "webhook_repository")
    try:
        target = await repository.disable_target(
            tenant_id=_tenant(auth), target_id=target_id, auth=auth
        )
    except WebhookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WebhookAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _target_view(target)


@router.post("/v1/conversations/{call_id}/review")
async def decide_conversation_review(
    call_id: UUID, body: ReviewDecisionBody, request: Request, auth: ReviewDecider
) -> dict[str, Any]:
    tenant_id = _tenant(auth)
    jobs = _state(request, "post_call_job_repository")
    reviews = _state(request, "review_repository")
    result = await jobs.get_result(tenant_id, call_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No intelligence result for this conversation.")
    review = await jobs.get_review_for_result(tenant_id, result.result_id)
    if review is None:
        raise HTTPException(status_code=404, detail="This conversation needs no review.")
    try:
        decided = await reviews.decide(
            tenant_id=tenant_id,
            review_id=review.review_id,
            decision=ReviewDecision.APPROVE if body.decision == "approve" else ReviewDecision.REJECT,
            auth=auth,
            note=body.note.strip(),
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReviewAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    delivered = 0
    webhooks = getattr(request.app.state, "webhook_repository", None)
    if decided.state is ReviewState.APPROVED and webhooks is not None:
        delivered = await enqueue_for_result(
            webhooks,
            tenant_id=tenant_id,
            call_id=call_id,
            result_id=result.result_id,
            review_id=decided.review_id,
        )
    return {
        "review_id": str(decided.review_id),
        "state": decided.state.value,
        "decided_at": decided.decided_at.isoformat() if decided.decided_at else None,
        "webhook_deliveries_enqueued": delivered,
    }
