"""Example Customer Host Backend (Zero-Secret Mint Proxy)."""

from __future__ import annotations

import os
from typing import Any
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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
    payload = {
        "tenant_id": TENANT_ID,
        "agent_id": AGENT_ID,
        "caller_id": req.caller_id,
        "test_call": req.test_call,
    }
    headers = {
        "x-tenant-id": TENANT_ID,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{UCVE_CONTROL_PLANE}/v1/session/mint",
            json=payload,
            headers=headers,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to mint voice session.")
        return resp.json()  # Returns {session_id, token, ws_url}
