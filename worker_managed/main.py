"""UCVE Managed Worker Entrypoint (LiveKit bridge)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
import uvicorn

from core.observability.http import install_observability, observability_runtime
from core.runtime.health import CheckResult, ReadinessProbe, install_health_routes


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    async with observability_runtime(_app, "worker-managed"):
        yield


app = FastAPI(title="Wavia Managed Worker", version="0.1.0", lifespan=lifespan)


install_observability(app, "worker-managed")


async def _managed_runtime_check() -> CheckResult:
    # H05: LiveKit/managed transport is roadmap-only for v1. This process has
    # no session runtime, so it must never receive traffic.
    return CheckResult.fail(
        "managed_runtime", "LiveKit managed runtime is roadmap-only (not implemented)"
    )


readiness = ReadinessProbe("worker-managed")
readiness.add_check("managed_runtime", _managed_runtime_check)
install_health_routes(app, readiness)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "worker-managed"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "worker-managed", "mode": "livekit-managed"}


def main() -> None:
    port = int(os.environ.get("PORT", "8082"))
    uvicorn.run("worker_managed.main:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
