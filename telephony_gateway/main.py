"""UCVE Sovereign Telephony Gateway Entrypoint — HTTP health + carrier webhooks."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response, status

from core.db.http_errors import install_database_error_handlers
from core.observability.http import install_observability, observability_runtime
from core.runtime.health import (
    CheckResult,
    ReadinessProbe,
    database_check,
    install_health_routes,
    profile_check,
)
from telephony_gateway.telnyx.webhook import (
    TelnyxWebhookError,
    TelnyxWebhookService,
    build_telnyx_webhook_service,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    async with observability_runtime(_app, "telephony-gateway"):
        async with _gateway_lifespan(_app):
            yield


@asynccontextmanager
async def _gateway_lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    event_sink = getattr(_app.state, "telnyx_event_sink", None)
    database = None
    try:
        if (
            _app.state.telnyx_webhook_service is None
            and event_sink is None
            and os.environ.get("DATABASE_URL")
        ):
            from core.db.async_pg import AsyncDatabase
            from core.db.repos.telephony_repo import PostgresTelephonyRepository

            database = AsyncDatabase.from_environment()
            await database.open()
            _app.state.database = database
            event_sink = PostgresTelephonyRepository(database)
            _app.state.telnyx_event_sink = event_sink
        if _app.state.telnyx_webhook_service is None and event_sink is not None:
            _app.state.telnyx_webhook_service = build_telnyx_webhook_service(
                event_sink=event_sink
            )
        yield
    finally:
        if database is not None:
            await database.close()
            _app.state.database = None
            _app.state.telnyx_event_sink = None
            _app.state.telnyx_webhook_service = None


app = FastAPI(title="Wavia Telephony Gateway", version="0.1.0", lifespan=lifespan)
app.state.telnyx_webhook_service = None
app.state.telnyx_event_sink = None
app.state.database = None


install_observability(app, "telephony-gateway")
install_database_error_handlers(app)


async def _webhook_verifier_check() -> CheckResult:
    if getattr(app.state, "telnyx_webhook_service", None) is not None:
        return CheckResult.ok("telnyx_webhooks", "signature verifier configured")
    return CheckResult.fail(
        "telnyx_webhooks", "verifier unavailable (TELNYX_PUBLIC_KEY or event store missing)"
    )


readiness = ReadinessProbe("telephony-gateway")
readiness.add_check(
    "database", database_check(lambda: getattr(app.state, "database", None))
)
readiness.add_check("telnyx_webhooks", _webhook_verifier_check)
readiness.add_check("runtime_profile", profile_check)
install_health_routes(app, readiness)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "telephony-gateway"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "telephony-gateway", "version": "0.1.0"}


@app.post("/v1/telephony/webhooks/telnyx")
async def telnyx_webhook(
    request: Request,
    response: Response,
    telnyx_signature: str | None = Header(None, alias="telnyx-signature-ed25519"),
    telnyx_timestamp: str | None = Header(None, alias="telnyx-timestamp"),
) -> dict[str, Any]:
    service: TelnyxWebhookService | None = getattr(
        request.app.state, "telnyx_webhook_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "telnyx_verifier_unavailable"},
        )
    raw_body = await request.body()
    try:
        accepted = await service.accept(
            raw_body,
            signature_header=telnyx_signature,
            timestamp_header=telnyx_timestamp,
        )
    except TelnyxWebhookError as exc:
        code = (
            status.HTTP_401_UNAUTHORIZED
            if exc.code == "invalid_telnyx_signature"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail={"code": exc.code}) from exc
    response.status_code = (
        status.HTTP_200_OK if accepted.duplicate else status.HTTP_202_ACCEPTED
    )
    return {
        "status": "duplicate" if accepted.duplicate else "accepted",
        "event_id": str(accepted.event_id),
        "event_type": accepted.event_type.value,
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
