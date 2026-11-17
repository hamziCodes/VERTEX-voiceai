"""Tenant-scoped human-review repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from control_plane.auth.context import AuthContext
from control_plane.auth.rbac import actor_has_permission
from core.db.async_pg import AsyncDatabase, get_default_database
from post_call.review.models import ReviewDecision, ReviewRequest, ReviewState


class ReviewNotFoundError(LookupError):
    pass


class ReviewAuthorizationError(PermissionError):
    pass


class ReviewConflictError(RuntimeError):
    pass


class InMemoryReviewRepository:
    def __init__(self, backing: dict[UUID, ReviewRequest] | None = None) -> None:
        self._reviews = backing if backing is not None else {}

    async def create_pending(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        result_id: UUID,
        reasons: tuple[str, ...],
    ) -> ReviewRequest:
        if not reasons:
            raise ValueError("A pending review requires at least one reason.")
        for review in self._reviews.values():
            if review.tenant_id == tenant_id and review.result_id == result_id:
                return review.model_copy(deep=True)
        review = ReviewRequest(
            tenant_id=tenant_id,
            call_id=call_id,
            result_id=result_id,
            reasons=tuple(sorted(set(reasons))),
        )
        self._reviews[review.review_id] = review
        return review.model_copy(deep=True)

    async def decide(
        self,
        *,
        tenant_id: UUID,
        review_id: UUID,
        decision: ReviewDecision,
        auth: AuthContext,
        note: str,
    ) -> ReviewRequest:
        if auth.tenant_id != str(tenant_id):
            raise ReviewAuthorizationError("Review tenant does not match actor.")
        if not actor_has_permission(auth, "extraction:write"):
            raise ReviewAuthorizationError("Actor cannot decide extraction review.")
        review = self._reviews.get(review_id)
        if review is None or review.tenant_id != tenant_id:
            raise ReviewNotFoundError("Review request not found.")
        target = (
            ReviewState.APPROVED
            if decision is ReviewDecision.APPROVE
            else ReviewState.REJECTED
        )
        if review.state is not ReviewState.PENDING:
            if review.state is target and review.decided_by == auth.subject_id:
                return review.model_copy(deep=True)
            raise ReviewConflictError("Review decision is immutable.")
        review.state = target
        review.decided_by = auth.subject_id
        review.decision_note = note.strip()[:500] or None
        review.decided_at = datetime.now(UTC)
        return review.model_copy(deep=True)

    async def get_for_result(
        self, tenant_id: UUID, result_id: UUID
    ) -> ReviewRequest | None:
        for review in self._reviews.values():
            if review.tenant_id == tenant_id and review.result_id == result_id:
                return review.model_copy(deep=True)
        return None


def _authorize_decision(tenant_id: UUID, auth: AuthContext) -> None:
    if auth.tenant_id != str(tenant_id):
        raise ReviewAuthorizationError("Review tenant does not match actor.")
    if not actor_has_permission(auth, "extraction:write"):
        raise ReviewAuthorizationError("Actor cannot decide extraction review.")


class PostgresReviewRepository:
    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def decide(
        self,
        *,
        tenant_id: UUID,
        review_id: UUID,
        decision: ReviewDecision,
        auth: AuthContext,
        note: str,
    ) -> ReviewRequest:
        _authorize_decision(tenant_id, auth)
        target = (
            ReviewState.APPROVED
            if decision is ReviewDecision.APPROVE
            else ReviewState.REJECTED
        )
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT review_id, tenant_id, call_id, result_id, reasons_jsonb, "
                "state, decided_by, decision_note, created_at, decided_at "
                "FROM post_call_review_requests WHERE tenant_id = %s::uuid "
                "AND review_id = %s::uuid FOR UPDATE",
                (str(tenant_id), str(review_id)),
            )
            row = await cursor.fetchone()
            if row is None:
                raise ReviewNotFoundError("Review request not found.")
            current = ReviewState(row[5])
            if current is not ReviewState.PENDING:
                if current is target and row[6] == auth.subject_id:
                    return ReviewRequest(
                        review_id=row[0],
                        tenant_id=row[1],
                        call_id=row[2],
                        result_id=row[3],
                        reasons=tuple(row[4]),
                        state=current,
                        decided_by=row[6],
                        decision_note=row[7],
                        created_at=row[8],
                        decided_at=row[9],
                    )
                raise ReviewConflictError("Review decision is immutable.")
            decided_at = datetime.now(UTC)
            updated = await connection.execute(
                "UPDATE post_call_review_requests SET state = %s, decided_by = %s, "
                "decision_note = %s, decided_at = %s WHERE tenant_id = %s::uuid "
                "AND review_id = %s::uuid RETURNING review_id, tenant_id, call_id, "
                "result_id, reasons_jsonb, state, decided_by, decision_note, "
                "created_at, decided_at",
                (
                    target.value,
                    auth.subject_id,
                    note.strip()[:500] or None,
                    decided_at,
                    str(tenant_id),
                    str(review_id),
                ),
            )
            result = await updated.fetchone()
        return ReviewRequest(
            review_id=result[0],
            tenant_id=result[1],
            call_id=result[2],
            result_id=result[3],
            reasons=tuple(result[4]),
            state=result[5],
            decided_by=result[6],
            decision_note=result[7],
            created_at=result[8],
            decided_at=result[9],
        )
