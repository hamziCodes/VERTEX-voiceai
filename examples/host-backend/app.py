"""Example Customer Host Backend (Zero-Secret Mint Proxy)."""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from control_plane.auth.hmac_mint import expected_signature

app = FastAPI(title="Customer Host Backend Example")

UCVE_CONTROL_PLANE = os.environ.get("UCVE_CONTROL_PLANE_URL", "http://localhost:8080")
TENANT_ID = os.environ.get("UCVE_TENANT_ID", "00000000-0000-0000-0000-000000000001")
AGENT_ID = os.environ.get("UCVE_AGENT_ID", "00000000-0000-0000-0000-0000000000a1")


class SessionRequest(BaseModel):
    caller_id: str | None = None
    test_call: bool = False


@app.post("/api/voice/session")
async def create_voice_session(req: SessionRequest) -> dict[str, Any]:
    """Mint an ephemeral token on behalf of an authenticated web/mobile user.

    The client never sees or possesses the host's tenant master key.
    """
    del req  # Authenticate and authorize this request in the host application.
    secret = os.environ.get("UCVE_MINT_HMAC_SECRET")
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Host mint credentials are not configured.",
        )
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    headers = {
        "X-Tenant-Id": TENANT_ID,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Agent-Id": AGENT_ID,
        "X-Signature": expected_signature(
            secret, TENANT_ID, timestamp, nonce, AGENT_ID
        ),
    }
    origin = os.environ.get("UCVE_HOST_ORIGIN")
    if origin:
        headers["Origin"] = origin

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{UCVE_CONTROL_PLANE}/v1/session",
            headers=headers,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to mint voice session.")
        return resp.json()  # Returns {session_id, token, ws_url}
