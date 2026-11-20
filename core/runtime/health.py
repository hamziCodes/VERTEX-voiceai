"""Liveness and readiness for Wavia services (Phase 14).

``/health/live`` answers "is this process able to serve at all?" and never
touches dependencies, so an outage of PostgreSQL or Redis does not make an
orchestrator restart every pod. ``/health/ready`` answers "should traffic be
routed here now?" and runs the service's dependency checks, each bounded by a
timeout. ``/health`` stays as the legacy liveness alias used by existing
Dockerfile and compose health checks.

Rules:

- No check makes a paid or external provider request. Provider readiness is a
  configuration check only.
- Check details never include exception messages, connection strings or
  secret values; failures report the exception type.
- A draining process (SIGTERM received) is never ready.
- Protected environments (staging/production) treat missing required
  dependencies as failures; development/test report them as not configured.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from core.observability.metrics import ucve_readiness
from core.runtime.env import is_protected_environment, is_test_env

CheckFn = Callable[[], Awaitable["CheckResult"]]


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # "ok" | "fail"
    detail: str = ""

    @classmethod
    def ok(cls, name: str, detail: str = "") -> CheckResult:
        return cls(name=name, status="ok", detail=detail)

    @classmethod
    def fail(cls, name: str, detail: str) -> CheckResult:
        return cls(name=name, status="fail", detail=detail)


@dataclass
class _Registered:
    name: str
    fn: CheckFn
    required: bool


class ReadinessProbe:
    """Ordered set of dependency checks plus a draining flag."""

    def __init__(self, service: str, *, check_timeout_s: float = 2.0) -> None:
        self.service = service
        self.check_timeout_s = check_timeout_s
        self._checks: list[_Registered] = []
        self._draining = False

    @property
    def draining(self) -> bool:
        return self._draining

    def start_draining(self) -> None:
        self._draining = True

    def add_check(self, name: str, fn: CheckFn, *, required: bool = True) -> None:
        self._checks.append(_Registered(name=name, fn=fn, required=required))

    async def _run_one(self, check: _Registered) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(check.fn(), timeout=self.check_timeout_s)
            status, detail = result.status, result.detail
        except TimeoutError:
            status, detail = "fail", "timed out"
        except Exception as exc:  # noqa: BLE001 - reported by type only
            status, detail = "fail", type(exc).__name__
        ucve_readiness.labels(service=self.service, check=check.name).set(
            1.0 if status == "ok" else 0.0
        )
        return {
            "name": check.name,
            "status": status,
            "required": check.required,
            "detail": detail,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 2),
        }

    async def evaluate(self) -> tuple[int, dict[str, Any]]:
        results = list(await asyncio.gather(*(self._run_one(c) for c in self._checks)))
        required_failed = any(r["required"] and r["status"] != "ok" for r in results)
        optional_failed = any(
            not r["required"] and r["status"] != "ok" for r in results
        )
        if self._draining:
            status = "draining"
        elif required_failed:
            status = "not_ready"
        elif optional_failed:
            status = "degraded"
        else:
            status = "ready"
        code = 200 if status in {"ready", "degraded"} else 503
        return code, {"service": self.service, "status": status, "checks": results}


def install_health_routes(app: FastAPI, probe: ReadinessProbe) -> None:
    """Add ``/health/live`` and ``/health/ready`` (and ``/health`` if missing)."""
    app.state.readiness_probe = probe
    existing = {getattr(r, "path", None) for r in app.router.routes}

    @app.get("/health/live", include_in_schema=False)
    async def _live() -> dict[str, str]:
        return {"status": "alive", "service": probe.service}

    @app.get("/health/ready", include_in_schema=False)
    async def _ready() -> JSONResponse:
        code, body = await probe.evaluate()
        return JSONResponse(status_code=code, content=body)

    if "/health" not in existing:

        @app.get("/health", include_in_schema=False)
        async def _legacy() -> dict[str, str]:
            return {"status": "ok", "service": probe.service}


# --- Reusable checks ---------------------------------------------------------


def database_check(get_database: Callable[[], Any]) -> CheckFn:
    """``SELECT 1`` through the service's pool; in-memory mode is honest."""

    async def check() -> CheckResult:
        database = get_database()
        if database is None:
            if is_protected_environment():
                return CheckResult.fail("database", "not configured")
            return CheckResult.ok("database", "in-memory repositories (development)")
        pool = getattr(database, "pool", None)
        if pool is None:
            return CheckResult.fail("database", "pool not open")
        async with pool.connection() as connection:
            await connection.execute("SELECT 1")
        return CheckResult.ok("database")

    return check


_redis_clients: dict[str, Any] = {}


def redis_check() -> CheckFn:
    """PING the configured Redis; required in protected environments."""

    async def check() -> CheckResult:
        url = (os.environ.get("REDIS_URL") or "").strip()
        if not url:
            if is_protected_environment():
                return CheckResult.fail("redis", "not configured")
            return CheckResult.ok("redis", "not configured (development)")
        if is_test_env() and not is_protected_environment():
            return CheckResult.ok("redis", "skipped in test environment")
        client = _redis_clients.get(url)
        if client is None:
            from redis.asyncio import Redis

            client = Redis.from_url(url, socket_connect_timeout=1.5, socket_timeout=1.5)
            _redis_clients[url] = client
        await client.ping()
        return CheckResult.ok("redis")

    return check


async def profile_check() -> CheckResult:
    """The selected runtime profile must exist; no silent fallback to dev."""
    from core.runtime.profile_loader import ProfileNotFoundError, load_profile_strict

    try:
        profile = load_profile_strict()
    except ProfileNotFoundError:
        return CheckResult.fail("runtime_profile", "unknown UCVE_RUNTIME_PROFILE")
    return CheckResult.ok(
        "runtime_profile",
        f"{profile.name}: {profile.max_sessions_per_worker} sessions per worker",
    )


# Default routes from the approved provider plan (H07). Tenants may bring
# their own keys, so missing platform keys degrade rather than block.
_PLATFORM_PROVIDERS = {
    "stt": ("GLADIA", "DEEPGRAM"),
    "llm": ("GROQ", "GEMINI", "OPENAI"),
    "tts": ("CARTESIA", "ELEVENLABS", "UPLIFT"),
}


async def provider_configuration_check() -> CheckResult:
    """Report provider mode and platform-key coverage without any network call."""
    from core.providers.mode import provider_runtime_status

    mode = provider_runtime_status()["provider_mode"]
    if mode != "live":
        return CheckResult.ok("providers", "mock provider mode")
    missing = [
        category
        for category, providers in _PLATFORM_PROVIDERS.items()
        if not any(
            (os.getenv(f"PLATFORM_{p}_API_KEY") or "").strip() for p in providers
        )
    ]
    if missing:
        return CheckResult.fail(
            "providers",
            "live mode; no platform key configured for " + ", ".join(missing),
        )
    return CheckResult.ok(
        "providers", "live mode; platform keys configured (not probed)"
    )
