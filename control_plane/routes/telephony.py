"""Authenticated management routes for controlled telephony actions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import require_permission
from telephony_gateway.outbound import (
    OutboundCallError,
    OutboundCallRequest,
)

router = APIRouter(prefix="/telephony", tags=["telephony"])
TelephonyWriter = Annotated[
    AuthContext, Depends(require_permission("telephony:write"))
]


class OutboundCallBody(BaseModel):
    agent_id: UUID
    destination: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")
    purpose: str = Field(min_length=1, max_length=120)
    consent_reference: str = Field(min_length=1, max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=255)


_STATUS_BY_ERROR = {
    "idempotency_conflict": 409,
    "destination_not_allowed": 403,
    "outside_calling_window": 403,
    "concurrency_limit": 429,
    "rate_limit": 429,
    "spend_limit": 429,
    "outbound_setup_unavailable": 503,
    "outbound_setup_not_ready": 503,
    "outbound_policy_unavailable": 503,
    "outbound_policy_invalid": 503,
    "outbound_provider_unavailable": 503,
    "live_telephony_disabled": 503,
    "carrier_unavailable": 503,
    "carrier_rate_limited": 503,
    "carrier_request_failed": 503,
    "carrier_request_rejected": 502,
    "invalid_carrier_response": 502,
    "carrier_result_ambiguous": 503,
}


@router.post("/calls", status_code=202)
async def create_outbound_call(
    body: OutboundCallBody,
    request: Request,
    auth: TelephonyWriter,
) -> dict[str, str | None]:
    """Create one consented, policy-gated outbound call request."""

    service = getattr(request.app.state, "outbound_call_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Outbound calling is unavailable.")
    try:
        result = await service.create_call(
            OutboundCallRequest(
                tenant_id=UUID(auth.tenant_id),
                agent_id=body.agent_id,
                destination=body.destination,
                purpose=body.purpose,
                consent_reference=body.consent_reference,
                idempotency_key=body.idempotency_key,
            )
        )
    except OutboundCallError as exc:
        raise HTTPException(
            status_code=_STATUS_BY_ERROR.get(exc.code, 422), detail=exc.code
        ) from exc
    return {
        "request_id": str(result.request_id),
        "status": result.status.value,
        "call_control_id": result.call_control_id,
    }
