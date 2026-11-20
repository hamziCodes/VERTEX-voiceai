from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from post_call.webhook.models import TenantWebhookTarget, WebhookTargetState
from post_call.webhook.policy import WebhookEndpointPolicy, WebhookSecurityError


def test_target_persists_credential_reference_and_rejects_raw_secret() -> None:
    target = TenantWebhookTarget(
        tenant_id=uuid4(),
        name="Primary CRM",
        url="https://crm.example.test/events",
        credential_ref="crm-signing-v1",
    )

    assert target.state is WebhookTargetState.PENDING
    assert "secret" not in target.model_dump()
    with pytest.raises(ValidationError):
        TenantWebhookTarget.model_validate(
            {
                **target.model_dump(),
                "secret": "must-not-be-stored",
            }
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://crm.example.test/events",
        "https://localhost/events",
        "https://127.0.0.1/events",
        "https://169.254.169.254/latest/meta-data",
        "https://user:password@crm.example.test/events",
        "https://crm.example.test/events#fragment",
    ],
)
async def test_policy_rejects_untrusted_destinations(url: str) -> None:
    policy = WebhookEndpointPolicy(resolver=lambda _host: ("93.184.216.34",))

    with pytest.raises(WebhookSecurityError):
        await policy.validate(url)


@pytest.mark.asyncio
async def test_policy_detects_dns_answer_change_after_review() -> None:
    answers = iter([("93.184.216.34",), ("93.184.216.35",)])
    policy = WebhookEndpointPolicy(resolver=lambda _host: next(answers))
    url = "https://crm.example.test/events"

    reviewed = await policy.validate(url)
    with pytest.raises(WebhookSecurityError, match="changed"):
        await policy.validate(url, expected_addresses=reviewed)


def test_active_target_requires_review_evidence_and_approved_addresses() -> None:
    with pytest.raises(ValidationError):
        TenantWebhookTarget(
            tenant_id=uuid4(),
            name="CRM",
            url="https://crm.example.test/events",
            credential_ref="crm-signing-v1",
            state=WebhookTargetState.ACTIVE,
        )

    target = TenantWebhookTarget(
        tenant_id=uuid4(),
        name="CRM",
        url="https://crm.example.test/events",
        credential_ref="crm-signing-v1",
        state=WebhookTargetState.ACTIVE,
        reviewed_by="operator-1",
        reviewed_at=datetime.now(UTC),
        approved_addresses=("93.184.216.34",),
    )
    assert target.state is WebhookTargetState.ACTIVE
