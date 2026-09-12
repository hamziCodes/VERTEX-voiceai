"""UCVE Sovereign Telephony Gateway Entrypoint — HTTP health + carrier webhooks."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request

from telephony_gateway.webhook_normalizer import WebhookNormalizer


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(title="UCVE Telephony Gateway", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "telephony-gateway"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "telephony-gateway", "version": "0.1.0"}


@app.post("/v1/telephony/webhook/{carrier}")
async def carrier_webhook(carrier: str, request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    event = WebhookNormalizer.normalize(carrier, body)
    return {
        "status": "processed",
        "carrier": carrier,
        "event_type": event.event_type.value,
        "session_id": str(event.session_id),
    }


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8083"))
    uvicorn.run(
        "telephony_gateway.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
