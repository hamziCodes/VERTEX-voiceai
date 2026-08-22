"""Control Plane Telephony Router — Telnyx webhooks & DID routing endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response

from telephony_gateway.telnyx.webhook import TelnyxWebhookHandler

router = APIRouter(prefix="/telephony", tags=["telephony"])
handler = TelnyxWebhookHandler()


@router.post("/telnyx/webhook")
async def telnyx_webhook(
    request: Request,
    telnyx_signature: str | None = Header(None, alias="telnyx-signature-ed25519"),
    telnyx_timestamp: str | None = Header(None, alias="telnyx-timestamp"),
) -> dict[str, Any]:
    """Inbound Telnyx PSTN webhook handler.

    Validates signature, resolves destination DID to (tenant_id, agent_id), and returns session mint.
    """
    body = await request.body()
    try:
        payload_json = await request.json()
    except Exception:
        payload_json = {}

    try:
        result = handler.process_event(
            payload_bytes=body,
            payload_json=payload_json,
            signature_header=telnyx_signature,
            timestamp_header=telnyx_timestamp,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
