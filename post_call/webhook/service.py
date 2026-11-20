"""Webhook target approval and one-attempt delivery worker."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from control_plane.auth.context import AuthContext
from post_call.webhook.dispatcher import WebhookDispatcher
from post_call.webhook.models import TenantWebhookTarget
from post_call.webhook.policy import WebhookEndpointPolicy


class WebhookTargetManager:
    def __init__(self, *, repository: Any, endpoint_policy: WebhookEndpointPolicy):
        self.repository = repository
        self.endpoint_policy = endpoint_policy

    async def create_and_approve(
        self,
        *,
        tenant_id: UUID,
        name: str,
        url: str,
        credential_ref: str,
        auth: AuthContext,
    ) -> TenantWebhookTarget:
        addresses = await self.endpoint_policy.validate(url)
        target = await self.repository.create_target(
            tenant_id=tenant_id,
            name=name,
            url=url,
            credential_ref=credential_ref,
            auth=auth,
        )
        return cast(
            TenantWebhookTarget,
            await self.repository.approve_target(
                tenant_id=tenant_id,
                target_id=target.target_id,
                auth=auth,
                approved_addresses=tuple(sorted(addresses)),
            ),
        )


class WebhookDeliveryWorker:
    def __init__(
        self,
        *,
        repository: Any,
        dispatcher: WebhookDispatcher,
        worker_id: str,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        self.repository = repository
        self.dispatcher = dispatcher
        self.worker_id = worker_id

    async def run_once(self, *, now: datetime | None = None) -> bool:
        delivery = await self.repository.claim_next(self.worker_id, now=now)
        if delivery is None:
            return False
        target = await self.repository.get_target(
            delivery.tenant_id, delivery.target_id
        )
        result = await self.dispatcher.send_once(target, delivery)
        await self.repository.record_attempt(
            delivery.delivery_id,
            worker_id=self.worker_id,
            result=result,
            now=now,
        )
        return True
