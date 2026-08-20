"""Local host-backend HMAC mint proxy for the AudioWorklet demo (not Phase 28 SDK)."""

from __future__ import annotations

import os
import time
import uuid

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from control_plane.auth.hmac_mint import expected_signature

app = FastAPI(title="UCVE Demo Host Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class MintRequest(BaseModel):
    tenant_id: str
    agent_id: str


@app.post("/mint")
async def mint(body: MintRequest) -> dict:
    secret = os.environ.get("UCVE_MINT_HMAC_SECRET", "dev-mint-secret")
    cp = os.environ.get("UCVE_CONTROL_PLANE_URL", "http://127.0.0.1:8080")
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    sig = expected_signature(secret, body.tenant_id, ts, nonce, body.agent_id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{cp.rstrip('/')}/v1/session",
            headers={
                "X-Tenant-Id": body.tenant_id,
                "X-Timestamp": ts,
                "X-Nonce": nonce,
                "X-Agent-Id": body.agent_id,
                "X-Signature": sig,
                "Origin": os.environ.get("UCVE_DEMO_ORIGIN", "http://127.0.0.1:5173"),
            },
        )
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090)
