"""Customer privacy operations: legal hold, conversation deletion, erasure.

All three need durable storage; without a database they answer 503 rather than
pretending. Deletion is asynchronous: requests return ``202`` with a job that
the jobs runner executes (objects first, then rows, re-checking legal holds),
and ``GET /v1/privacy-jobs/{job_id}`` reports its state and append-only event
trail. Workspace erasure keeps only an anonymous tombstone, the deletion event
record and staff audit; it requires typing the workspace name.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import require_permission
from core.compliance.audit.writer import AuditWriter
from core.compliance.privacy_jobs import PrivacyDeletionJob, PrivacyJobConflictError

router = APIRouter(tags=["privacy"])
HoldManager = Annotated[AuthContext, Depends(require_permission("legal_hold:manage"))]
Eraser = Annotated[AuthContext, Depends(require_permission("erasure:execute"))]


class LegalHoldBody(BaseModel):
    hold: bool
    reason: str = Field(min_length=8, max_length=500)


class WorkspaceErasureBody(BaseModel):
    confirm_workspace_name: str = Field(min_length=1, max_length=255)


def _repository(request: Request) -> Any:
    repository = getattr(request.app.state, "privacy_repository", None)
    if repository is None:
        raise HTTPException(
            status_code=503,
            detail="Privacy operations require durable storage in this environment.",
        )
    return repository


def _tenant(auth: AuthContext) -> UUID:
    return UUID(auth.tenant_id)


def _actor(auth: AuthContext) -> str:
    return f"{auth.auth_method}:{auth.subject_id}"


def _job_view(job: PrivacyDeletionJob) -> dict[str, Any]:
    return {
        "job_id": str(job.job_id),
        "kind": job.kind.value,
        "call_id": str(job.call_id) if job.call_id else None,
        "state": job.state.value,
        "attempts": job.attempt_count,
        "last_error_code": job.last_error_code,
        "objects_total": len(job.object_references),
        "objects_deleted": len(job.completed_object_references),
        "database_deleted": job.database_deleted,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


async def _audit(
    request: Request,
    auth: AuthContext,
    action: str,
    resource: str,
    detail: dict[str, Any],
) -> None:
    database = getattr(request.app.state, "database", None)
    await AuditWriter(database=database).arecord(
        auth.tenant_id,
        action,
        "privacy",
        resource,
        actor_id=auth.subject_id,
        actor_type=auth.auth_method,
        detail=detail,
    )


@router.post("/v1/conversations/{call_id}/legal-hold")
async def set_legal_hold(
    call_id: UUID, body: LegalHoldBody, request: Request, auth: HoldManager
) -> dict[str, Any]:
    repository = _repository(request)
    found = await repository.set_legal_hold(
        _tenant(auth), call_id, hold=body.hold, actor=_actor(auth)
    )
    if not found:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    await _audit(
        request,
        auth,
        "legal_hold_set" if body.hold else "legal_hold_released",
        str(call_id),
        {"reason": body.reason},
    )
    return {"call_id": str(call_id), "legal_hold": body.hold}


@router.post(
    "/v1/conversations/{call_id}/deletion", status_code=status.HTTP_202_ACCEPTED
)
async def request_conversation_deletion(
    call_id: UUID, request: Request, auth: Eraser
) -> dict[str, Any]:
    repository = _repository(request)
    try:
        job = await repository.request_call_deletion(
            _tenant(auth), call_id, actor=_actor(auth)
        )
    except PrivacyJobConflictError as exc:
        raise HTTPException(
            status_code=409, detail="This conversation is under legal hold."
        ) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    await _audit(
        request,
        auth,
        "data_erasure_requested",
        str(call_id),
        {"job_id": str(job.job_id)},
    )
    return _job_view(job)


@router.post("/v1/workspace/erasure", status_code=status.HTTP_202_ACCEPTED)
async def request_workspace_erasure(
    body: WorkspaceErasureBody, request: Request, auth: Eraser
) -> dict[str, Any]:
    repository = _repository(request)
    tenant_repo = request.app.state.mint_ctx.tenant_repo
    tenant = await tenant_repo.get_tenant(auth.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    if body.confirm_workspace_name.strip() != str(tenant.name).strip():
        raise HTTPException(
            status_code=422,
            detail="Type the workspace name exactly to confirm erasure.",
        )
    await _audit(request, auth, "workspace_erasure_requested", auth.tenant_id, {})
    job = await repository.request_tenant_erasure(_tenant(auth), actor=_actor(auth))
    return _job_view(job)


@router.get("/v1/privacy-jobs/{job_id}")
async def get_privacy_job(
    job_id: UUID, request: Request, auth: Eraser
) -> dict[str, Any]:
    repository = _repository(request)
    try:
        job = await repository.get_for_tenant(_tenant(auth), job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Privacy job not found.") from exc
    return {**_job_view(job), "events": await repository.events(job_id)}
