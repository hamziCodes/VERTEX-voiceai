from __future__ import annotations

from uuid import uuid4

import pytest

from control_plane.auth.context import AuthContext
from post_call.extraction.schema import ExtractionField, TenantExtractionSchema
from post_call.extraction.service import ExtractedField, ExtractionResult
from post_call.models.policy import PostCallPolicy
from post_call.review.models import ReviewDecision, ReviewState
from post_call.review.policy import ReviewPolicy
from post_call.review.repository import (
    InMemoryReviewRepository,
    ReviewAuthorizationError,
    ReviewConflictError,
)


def _auth(tenant_id: str, *scopes: str) -> AuthContext:
    return AuthContext(
        subject_id="reviewer-1",
        tenant_id=tenant_id,
        roles=("tenant_admin",),
        scopes=frozenset(scopes),
        auth_method="oidc",
    )


def test_review_policy_blocks_sensitive_uncertain_and_configured_actions() -> None:
    schema = TenantExtractionSchema(
        tenant_id=uuid4(),
        fields=[
            ExtractionField(name="patient_name", sensitive=True),
            ExtractionField(name="appointment_date", confidence_threshold=0.8),
        ],
    )
    result = ExtractionResult(
        fields={
            "patient_name": ExtractedField(
                value="Ayesha",
                confidence=0.99,
                source_turn_ids=(0,),
            ),
            "appointment_date": ExtractedField(
                value="Tuesday",
                confidence=0.6,
                source_turn_ids=(0,),
            ),
        },
        provider_id="fixture",
        model_id="fixture-v1",
    )

    reasons = ReviewPolicy().reasons(
        policy=PostCallPolicy(requires_review_for_external_actions=True),
        schema=schema,
        extraction=result,
        verification_issue_codes=(),
        external_action_configured=True,
    )

    assert set(reasons) == {
        "external_action_policy",
        "sensitive_field:patient_name",
        "low_confidence:appointment_date",
    }


def test_configured_external_action_cannot_disable_human_review() -> None:
    reasons = ReviewPolicy().reasons(
        policy=PostCallPolicy(requires_review_for_external_actions=False),
        schema=None,
        extraction=None,
        verification_issue_codes=(),
        external_action_configured=True,
    )

    assert reasons == ("external_action_policy",)


@pytest.mark.asyncio
async def test_review_decision_requires_tenant_scope_and_is_idempotent() -> None:
    repo = InMemoryReviewRepository()
    tenant_id = uuid4()
    request = await repo.create_pending(
        tenant_id=tenant_id,
        call_id=uuid4(),
        result_id=uuid4(),
        reasons=("sensitive_field:patient_name",),
    )

    with pytest.raises(ReviewAuthorizationError):
        await repo.decide(
            tenant_id=tenant_id,
            review_id=request.review_id,
            decision=ReviewDecision.APPROVE,
            auth=_auth(str(uuid4()), "extraction:write"),
            note="reviewed",
        )
    with pytest.raises(ReviewAuthorizationError):
        await repo.decide(
            tenant_id=tenant_id,
            review_id=request.review_id,
            decision=ReviewDecision.APPROVE,
            auth=_auth(str(tenant_id), "extraction:read"),
            note="reviewed",
        )

    approved = await repo.decide(
        tenant_id=tenant_id,
        review_id=request.review_id,
        decision=ReviewDecision.APPROVE,
        auth=_auth(str(tenant_id), "extraction:write"),
        note="reviewed",
    )
    duplicate = await repo.decide(
        tenant_id=tenant_id,
        review_id=request.review_id,
        decision=ReviewDecision.APPROVE,
        auth=_auth(str(tenant_id), "extraction:write"),
        note="reviewed",
    )

    assert approved.state is ReviewState.APPROVED
    assert duplicate == approved
    with pytest.raises(ReviewConflictError):
        await repo.decide(
            tenant_id=tenant_id,
            review_id=request.review_id,
            decision=ReviewDecision.REJECT,
            auth=_auth(str(tenant_id), "extraction:write"),
            note="changed",
        )
