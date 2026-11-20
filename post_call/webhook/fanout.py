"""Enqueue signed webhook deliveries for a completed post-call result.

Called when intelligence completes for a result the review policy did not
flag (``review_id=None``), and when a person approves a flagged result's
review (``review_id`` of that approval). One delivery per active target;
the repository enforces the review gate and idempotency, so repeating a call
is harmless.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from post_call.webhook.models import WebhookTargetState
from post_call.webhook.repository import (
    WebhookReviewRequiredError,
    WebhookTargetInactiveError,
)

EVENT_TYPE = "post_call.intelligence.completed"
logger = logging.getLogger("ucve.post_call.webhooks")


async def enqueue_for_result(
    repository: Any,
    *,
    tenant_id: UUID,
    call_id: UUID,
    result_id: UUID,
    review_id: UUID | None = None,
) -> int:
    enqueued = 0
    for target in await repository.list_targets(tenant_id):
        if target.state is not WebhookTargetState.ACTIVE:
            continue
        try:
            await repository.enqueue_delivery(
                tenant_id=tenant_id,
                target_id=target.target_id,
                call_id=call_id,
                result_id=result_id,
                review_id=review_id,
                event_type=EVENT_TYPE,
            )
        except (WebhookTargetInactiveError, WebhookReviewRequiredError) as exc:
            logger.info("webhook delivery not enqueued", extra={"reason": type(exc).__name__})
            continue
        enqueued += 1
    return enqueued
