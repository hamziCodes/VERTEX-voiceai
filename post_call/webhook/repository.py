"""Durable webhook target, delivery, and attempt repositories."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from control_plane.auth.context import AuthContext
from core.db.async_pg import AsyncDatabase, get_default_database
from post_call.jobs.models import PostCallIntelligenceResult
from post_call.review.models import ReviewState
from post_call.webhook.dispatcher import WebhookAttemptResult
from post_call.webhook.models import (
    TenantWebhookTarget,
    WebhookAttemptOutcome,
    WebhookDelivery,
    WebhookDeliveryAttempt,
    WebhookDeliveryState,
    WebhookTargetState,
)


class WebhookNotFoundError(LookupError):
    pass


class WebhookAuthorizationError(PermissionError):
    pass


class WebhookTargetInactiveError(RuntimeError):
    pass


class WebhookReviewRequiredError(PermissionError):
    pass


class WebhookLeaseConflictError(RuntimeError):
    pass


class WebhookPayloadConflictError(RuntimeError):
    pass


def logical_idempotency_key(
    tenant_id: UUID, target_id: UUID, call_id: UUID, event_type: str
) -> str:
    canonical = f"{tenant_id}:{target_id}:{call_id}:{event_type}".encode()
    return hashlib.sha256(canonical).hexdigest()


def build_delivery_payload(result: PostCallIntelligenceResult) -> dict[str, Any]:
    return {
        "schema_version": "wavia.post_call.intelligence.v1",
        "call_id": str(result.call_id),
        "result_id": str(result.result_id),
        "extraction": result.extraction,
        "summary": result.summary,
        "verification_issue_codes": list(result.verification_issue_codes),
    }


def _authorize(tenant_id: UUID, auth: AuthContext) -> None:
    if not auth.is_platform_admin and auth.tenant_id != str(tenant_id):
        raise WebhookAuthorizationError("Webhook tenant does not match actor.")
    if not auth.is_platform_admin and not (
        "*" in auth.scopes or "webhook:write" in auth.scopes
    ):
        raise WebhookAuthorizationError("Actor cannot manage webhook targets.")


def _validate_event_type(event_type: str) -> None:
    if event_type != "post_call.intelligence.completed":
        raise ValueError("Unsupported webhook event type.")


class InMemoryWebhookRepository:
    def __init__(self, *, review_repository: Any, intelligence_repository: Any) -> None:
        self.review_repository = review_repository
        self.intelligence_repository = intelligence_repository
        self._targets: dict[UUID, TenantWebhookTarget] = {}
        self._deliveries: dict[UUID, WebhookDelivery] = {}
        self._attempts: dict[UUID, list[WebhookDeliveryAttempt]] = {}

    async def create_target(
        self,
        *,
        tenant_id: UUID,
        name: str,
        url: str,
        credential_ref: str,
        auth: AuthContext,
        now: datetime | None = None,
    ) -> TenantWebhookTarget:
        _authorize(tenant_id, auth)
        target = TenantWebhookTarget(
            tenant_id=tenant_id,
            name=name,
            url=url,
            credential_ref=credential_ref,
            created_at=now or datetime.now(UTC),
            updated_at=now or datetime.now(UTC),
        )
        self._targets[target.target_id] = target
        return target.model_copy(deep=True)

    async def approve_target(
        self,
        *,
        tenant_id: UUID,
        target_id: UUID,
        auth: AuthContext,
        approved_addresses: tuple[str, ...],
        now: datetime | None = None,
    ) -> TenantWebhookTarget:
        _authorize(tenant_id, auth)
        target = self._targets.get(target_id)
        if target is None or target.tenant_id != tenant_id:
            raise WebhookNotFoundError("Webhook target not found.")
        if not approved_addresses:
            raise ValueError("Approved addresses are required.")
        timestamp = now or datetime.now(UTC)
        if target.state is WebhookTargetState.ACTIVE:
            return target.model_copy(deep=True)
        approved = target.model_copy(
            update={
                "state": WebhookTargetState.ACTIVE,
                "reviewed_by": auth.subject_id,
                "reviewed_at": timestamp,
                "approved_addresses": tuple(sorted(set(approved_addresses))),
                "updated_at": timestamp,
            }
        )
        self._targets[target_id] = approved
        return approved.model_copy(deep=True)

    async def get_target(self, tenant_id: UUID, target_id: UUID) -> TenantWebhookTarget:
        target = self._targets.get(target_id)
        if target is None or target.tenant_id != tenant_id:
            raise WebhookNotFoundError("Webhook target not found.")
        return target.model_copy(deep=True)

    async def enqueue_delivery(
        self,
        *,
        tenant_id: UUID,
        target_id: UUID,
        call_id: UUID,
        result_id: UUID,
        review_id: UUID,
        event_type: str,
        max_attempts: int = 3,
        now: datetime | None = None,
    ) -> WebhookDelivery:
        _validate_event_type(event_type)
        target = await self.get_target(tenant_id, target_id)
        if target.state is not WebhookTargetState.ACTIVE:
            raise WebhookTargetInactiveError("Webhook target is not active.")
        review = await self.review_repository.get_for_result(tenant_id, result_id)
        if (
            review is None
            or review.review_id != review_id
            or review.call_id != call_id
            or review.state is not ReviewState.APPROVED
        ):
            raise WebhookReviewRequiredError(
                "Approved review is required before webhook delivery."
            )
        result = await self.intelligence_repository.get_result(tenant_id, call_id)
        if result is None or result.result_id != result_id:
            raise WebhookNotFoundError("Approved intelligence result not found.")
        payload = build_delivery_payload(result)
        key = logical_idempotency_key(tenant_id, target_id, call_id, event_type)
        for existing in self._deliveries.values():
            if existing.tenant_id == tenant_id and existing.idempotency_key == key:
                if existing.payload != payload or existing.result_id != result_id:
                    raise WebhookPayloadConflictError(
                        "Logical webhook delivery already has different content."
                    )
                return existing.model_copy(deep=True)
        timestamp = now or datetime.now(UTC)
        delivery = WebhookDelivery(
            tenant_id=tenant_id,
            target_id=target_id,
            call_id=call_id,
            result_id=result_id,
            review_id=review_id,
            event_type=event_type,
            idempotency_key=key,
            payload=dict(payload),
            max_attempts=max_attempts,
            available_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._deliveries[delivery.delivery_id] = delivery
        self._attempts[delivery.delivery_id] = []
        return delivery.model_copy(deep=True)

    async def claim_next(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 30,
    ) -> WebhookDelivery | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        timestamp = now or datetime.now(UTC)
        for delivery in sorted(
            self._deliveries.values(), key=lambda item: item.created_at
        ):
            ready = (
                delivery.state
                in {WebhookDeliveryState.QUEUED, WebhookDeliveryState.RETRY_WAIT}
                and delivery.available_at <= timestamp
            )
            expired = (
                delivery.state is WebhookDeliveryState.RUNNING
                and delivery.lease_expires_at is not None
                and delivery.lease_expires_at <= timestamp
            )
            if not (ready or expired):
                continue
            claimed = delivery.model_copy(
                update={
                    "state": WebhookDeliveryState.RUNNING,
                    "lease_owner": worker_id,
                    "lease_expires_at": timestamp
                    + timedelta(seconds=max(1, lease_seconds)),
                    "updated_at": timestamp,
                }
            )
            self._deliveries[delivery.delivery_id] = claimed
            return claimed.model_copy(deep=True)
        return None

    async def record_attempt(
        self,
        delivery_id: UUID,
        *,
        worker_id: str,
        result: WebhookAttemptResult,
        now: datetime | None = None,
    ) -> WebhookDelivery:
        delivery = self._deliveries.get(delivery_id)
        if delivery is None:
            raise WebhookNotFoundError("Webhook delivery not found.")
        if (
            delivery.state is not WebhookDeliveryState.RUNNING
            or delivery.lease_owner != worker_id
        ):
            raise WebhookLeaseConflictError(
                "Webhook delivery lease is not owned by worker."
            )
        timestamp = now or datetime.now(UTC)
        attempt_count = delivery.attempt_count + 1
        if result.succeeded:
            state = WebhookDeliveryState.SUCCEEDED
            outcome = WebhookAttemptOutcome.SUCCEEDED
            available_at = timestamp
        elif result.retryable and attempt_count < delivery.max_attempts:
            state = WebhookDeliveryState.RETRY_WAIT
            outcome = WebhookAttemptOutcome.RETRYABLE_FAILURE
            available_at = timestamp + timedelta(
                seconds=min(300, 2 ** (attempt_count - 1))
            )
        else:
            state = WebhookDeliveryState.DEAD_LETTER
            outcome = WebhookAttemptOutcome.TERMINAL_FAILURE
            available_at = timestamp
        attempt = WebhookDeliveryAttempt(
            tenant_id=delivery.tenant_id,
            delivery_id=delivery.delivery_id,
            attempt_number=attempt_count,
            outcome=outcome,
            status_code=result.status_code,
            error_code=result.error_code,
            duration_ms=result.duration_ms,
            created_at=timestamp,
        )
        updated = delivery.model_copy(
            update={
                "state": state,
                "attempt_count": attempt_count,
                "available_at": available_at,
                "lease_owner": None,
                "lease_expires_at": None,
                "last_status_code": result.status_code,
                "last_error_code": result.error_code,
                "updated_at": timestamp,
            }
        )
        self._attempts[delivery_id].append(attempt)
        self._deliveries[delivery_id] = updated
        return updated.model_copy(deep=True)

    async def get_delivery(self, tenant_id: UUID, delivery_id: UUID) -> WebhookDelivery:
        delivery = self._deliveries.get(delivery_id)
        if delivery is None or delivery.tenant_id != tenant_id:
            raise WebhookNotFoundError("Webhook delivery not found.")
        return delivery.model_copy(deep=True)

    async def list_attempts(
        self, tenant_id: UUID, delivery_id: UUID
    ) -> list[WebhookDeliveryAttempt]:
        await self.get_delivery(tenant_id, delivery_id)
        return [item.model_copy(deep=True) for item in self._attempts[delivery_id]]


class PostgresWebhookRepository:
    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    @staticmethod
    def _target_from_row(row: Any) -> TenantWebhookTarget:
        return TenantWebhookTarget(
            target_id=row[0],
            tenant_id=row[1],
            name=row[2],
            url=row[3],
            credential_ref=row[4],
            state=row[5],
            reviewed_by=row[6],
            reviewed_at=row[7],
            approved_addresses=tuple(row[8] or ()),
            created_at=row[9],
            updated_at=row[10],
        )

    @staticmethod
    def _delivery_from_row(row: Any) -> WebhookDelivery:
        return WebhookDelivery(
            delivery_id=row[0],
            tenant_id=row[1],
            target_id=row[2],
            call_id=row[3],
            result_id=row[4],
            review_id=row[5],
            event_type=row[6],
            idempotency_key=row[7],
            payload=row[8],
            state=row[9],
            attempt_count=row[10],
            max_attempts=row[11],
            available_at=row[12],
            lease_owner=row[13],
            lease_expires_at=row[14],
            last_status_code=row[15],
            last_error_code=row[16],
            created_at=row[17],
            updated_at=row[18],
        )

    @staticmethod
    def _target_select() -> str:
        return (
            "target_id, tenant_id, name, url, credential_ref, state, "
            "reviewed_by, reviewed_at, approved_addresses, created_at, updated_at"
        )

    @staticmethod
    def _delivery_select() -> str:
        return (
            "delivery_id, tenant_id, target_id, call_id, result_id, review_id, "
            "event_type, idempotency_key, payload_jsonb, state, attempt_count, "
            "max_attempts, available_at, lease_owner, lease_expires_at, "
            "last_status_code, last_error_code, created_at, updated_at"
        )

    async def create_target(
        self,
        *,
        tenant_id: UUID,
        name: str,
        url: str,
        credential_ref: str,
        auth: AuthContext,
        now: datetime | None = None,
    ) -> TenantWebhookTarget:
        _authorize(tenant_id, auth)
        timestamp = now or datetime.now(UTC)
        target = TenantWebhookTarget(
            tenant_id=tenant_id,
            name=name,
            url=url,
            credential_ref=credential_ref,
            created_at=timestamp,
            updated_at=timestamp,
        )
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "INSERT INTO post_call_webhook_targets "
                "(target_id, tenant_id, name, url, credential_ref, created_at, "
                "updated_at) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s) "
                "RETURNING " + self._target_select(),
                (
                    str(target.target_id),
                    str(tenant_id),
                    target.name,
                    target.url,
                    target.credential_ref,
                    timestamp,
                    timestamp,
                ),
            )
            row = await cursor.fetchone()
        return self._target_from_row(row)

    async def approve_target(
        self,
        *,
        tenant_id: UUID,
        target_id: UUID,
        auth: AuthContext,
        approved_addresses: tuple[str, ...],
        now: datetime | None = None,
    ) -> TenantWebhookTarget:
        _authorize(tenant_id, auth)
        if not approved_addresses:
            raise ValueError("Approved addresses are required.")
        timestamp = now or datetime.now(UTC)
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "UPDATE post_call_webhook_targets SET state = 'active', "
                "reviewed_by = %s, "
                "reviewed_at = %s, approved_addresses = %s::jsonb, updated_at = %s "
                "WHERE tenant_id = %s::uuid AND target_id = %s::uuid "
                "RETURNING " + self._target_select(),
                (
                    auth.subject_id,
                    timestamp,
                    json.dumps(sorted(set(approved_addresses))),
                    timestamp,
                    str(tenant_id),
                    str(target_id),
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WebhookNotFoundError("Webhook target not found.")
        return self._target_from_row(row)

    async def get_target(self, tenant_id: UUID, target_id: UUID) -> TenantWebhookTarget:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._target_select()
                + " FROM post_call_webhook_targets WHERE tenant_id = %s::uuid "
                "AND target_id = %s::uuid",
                (str(tenant_id), str(target_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WebhookNotFoundError("Webhook target not found.")
        return self._target_from_row(row)

    async def enqueue_delivery(
        self,
        *,
        tenant_id: UUID,
        target_id: UUID,
        call_id: UUID,
        result_id: UUID,
        review_id: UUID,
        event_type: str,
        max_attempts: int = 3,
        now: datetime | None = None,
    ) -> WebhookDelivery:
        _validate_event_type(event_type)
        timestamp = now or datetime.now(UTC)
        key = logical_idempotency_key(tenant_id, target_id, call_id, event_type)
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            gate = await connection.execute(
                "SELECT t.state, r.state, r.call_id, r.result_id "
                "FROM post_call_webhook_targets t JOIN post_call_review_requests r "
                "ON r.tenant_id = t.tenant_id "
                "WHERE t.tenant_id = %s::uuid AND t.target_id = %s::uuid "
                "AND r.review_id = %s::uuid",
                (str(tenant_id), str(target_id), str(review_id)),
            )
            gate_row = await gate.fetchone()
            if gate_row is None:
                raise WebhookNotFoundError("Webhook target or review not found.")
            if gate_row[0] != WebhookTargetState.ACTIVE.value:
                raise WebhookTargetInactiveError("Webhook target is not active.")
            if (
                gate_row[1] != ReviewState.APPROVED.value
                or gate_row[2] != call_id
                or gate_row[3] != result_id
            ):
                raise WebhookReviewRequiredError(
                    "Approved review is required before webhook delivery."
                )
            result_cursor = await connection.execute(
                "SELECT result_id, tenant_id, call_id, extraction_jsonb, "
                "summary_jsonb, verification_issue_codes, provider_snapshot, "
                "created_at FROM post_call_intelligence_results "
                "WHERE tenant_id = %s::uuid AND call_id = %s::uuid "
                "AND result_id = %s::uuid",
                (str(tenant_id), str(call_id), str(result_id)),
            )
            result_row = await result_cursor.fetchone()
            if result_row is None:
                raise WebhookNotFoundError("Approved intelligence result not found.")
            payload = build_delivery_payload(
                PostCallIntelligenceResult(
                    result_id=result_row[0],
                    tenant_id=result_row[1],
                    call_id=result_row[2],
                    extraction=result_row[3],
                    summary=result_row[4],
                    verification_issue_codes=tuple(result_row[5] or ()),
                    provider_snapshot=result_row[6] or {},
                    created_at=result_row[7],
                )
            )
            cursor = await connection.execute(
                "INSERT INTO webhook_deliveries "
                "(tenant_id, target_id, call_id, result_id, review_id, event_type, "
                "idempotency_key, payload_jsonb, max_attempts, available_at, "
                "created_at, updated_at) VALUES "
                "(%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, "
                "%s::jsonb, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, target_id, call_id, event_type) "
                "DO UPDATE SET updated_at = webhook_deliveries.updated_at RETURNING "
                + self._delivery_select(),
                (
                    str(tenant_id),
                    str(target_id),
                    str(call_id),
                    str(result_id),
                    str(review_id),
                    event_type,
                    key,
                    json.dumps(payload),
                    max_attempts,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            row = await cursor.fetchone()
        delivery = self._delivery_from_row(row)
        if delivery.result_id != result_id or delivery.payload != payload:
            raise WebhookPayloadConflictError(
                "Logical webhook delivery already has different content."
            )
        return delivery

    async def claim_next(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 30,
    ) -> WebhookDelivery | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._delivery_select()
                + " FROM webhook_deliveries WHERE attempt_count < max_attempts AND "
                "(((state IN ('queued', 'retry_wait')) AND available_at <= %s) "
                "OR (state = 'running' AND lease_expires_at <= %s)) "
                "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1",
                (timestamp, timestamp),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            lease_expires = timestamp + timedelta(seconds=max(1, lease_seconds))
            updated = await connection.execute(
                "UPDATE webhook_deliveries SET state = 'running', lease_owner = %s, "
                "lease_expires_at = %s, updated_at = %s "
                "WHERE delivery_id = %s::uuid RETURNING " + self._delivery_select(),
                (worker_id, lease_expires, timestamp, str(row[0])),
            )
            claimed = await updated.fetchone()
        return self._delivery_from_row(claimed)

    async def record_attempt(
        self,
        delivery_id: UUID,
        *,
        worker_id: str,
        result: WebhookAttemptResult,
        now: datetime | None = None,
    ) -> WebhookDelivery:
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._delivery_select()
                + " FROM webhook_deliveries WHERE delivery_id = %s::uuid FOR UPDATE",
                (str(delivery_id),),
            )
            row = await cursor.fetchone()
            if row is None:
                raise WebhookNotFoundError("Webhook delivery not found.")
            delivery = self._delivery_from_row(row)
            if (
                delivery.state is not WebhookDeliveryState.RUNNING
                or delivery.lease_owner != worker_id
            ):
                raise WebhookLeaseConflictError(
                    "Webhook delivery lease is not owned by worker."
                )
            attempt_count = delivery.attempt_count + 1
            if result.succeeded:
                state = WebhookDeliveryState.SUCCEEDED
                outcome = WebhookAttemptOutcome.SUCCEEDED
                available_at = timestamp
            elif result.retryable and attempt_count < delivery.max_attempts:
                state = WebhookDeliveryState.RETRY_WAIT
                outcome = WebhookAttemptOutcome.RETRYABLE_FAILURE
                available_at = timestamp + timedelta(
                    seconds=min(300, 2 ** (attempt_count - 1))
                )
            else:
                state = WebhookDeliveryState.DEAD_LETTER
                outcome = WebhookAttemptOutcome.TERMINAL_FAILURE
                available_at = timestamp
            await connection.execute(
                "INSERT INTO webhook_delivery_attempts "
                "(tenant_id, delivery_id, attempt_number, outcome, status_code, "
                "error_code, duration_ms, created_at) VALUES "
                "(%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)",
                (
                    str(delivery.tenant_id),
                    str(delivery.delivery_id),
                    attempt_count,
                    outcome.value,
                    result.status_code,
                    result.error_code,
                    result.duration_ms,
                    timestamp,
                ),
            )
            updated = await connection.execute(
                "UPDATE webhook_deliveries SET state = %s, attempt_count = %s, "
                "available_at = %s, lease_owner = NULL, lease_expires_at = NULL, "
                "last_status_code = %s, last_error_code = %s, updated_at = %s "
                "WHERE delivery_id = %s::uuid RETURNING " + self._delivery_select(),
                (
                    state.value,
                    attempt_count,
                    available_at,
                    result.status_code,
                    result.error_code,
                    timestamp,
                    str(delivery_id),
                ),
            )
            updated_row = await updated.fetchone()
        return self._delivery_from_row(updated_row)

    async def get_delivery(self, tenant_id: UUID, delivery_id: UUID) -> WebhookDelivery:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._delivery_select()
                + " FROM webhook_deliveries WHERE tenant_id = %s::uuid "
                "AND delivery_id = %s::uuid",
                (str(tenant_id), str(delivery_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WebhookNotFoundError("Webhook delivery not found.")
        return self._delivery_from_row(row)

    async def list_attempts(
        self, tenant_id: UUID, delivery_id: UUID
    ) -> list[WebhookDeliveryAttempt]:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT attempt_id, tenant_id, delivery_id, attempt_number, "
                "outcome, status_code, error_code, duration_ms, created_at "
                "FROM webhook_delivery_attempts WHERE tenant_id = %s::uuid "
                "AND delivery_id = %s::uuid ORDER BY attempt_number",
                (str(tenant_id), str(delivery_id)),
            )
            rows = await cursor.fetchall()
        return [
            WebhookDeliveryAttempt(
                attempt_id=row[0],
                tenant_id=row[1],
                delivery_id=row[2],
                attempt_number=row[3],
                outcome=row[4],
                status_code=row[5],
                error_code=row[6],
                duration_ms=row[7],
                created_at=row[8],
            )
            for row in rows
        ]
