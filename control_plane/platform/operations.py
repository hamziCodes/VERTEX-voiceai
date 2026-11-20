"""Platform operations health snapshot (Phase 13K).

Built only from signals the control plane really has. It never calls a live
provider, carrier or identity provider, and never returns secret or
environment-variable values: only whether something is configured.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from inspect import isawaitable
from time import perf_counter
from typing import Any, Literal

from core.runtime.env import get_ucve_env

SignalStatus = Literal[
    "healthy", "attention", "not_configured", "disabled", "not_measured"
]
JOB_STATES = ("queued", "running", "retry_wait", "succeeded", "dead_letter")


def _signal(
    key: str,
    label: str,
    status: SignalStatus,
    detail: str,
    metrics: Mapping[str, int | float] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
        "metrics": dict(metrics or {}),
    }


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip() == "1"


async def _database_signal(state: Any) -> dict[str, Any]:
    database = getattr(state, "database", None)
    if database is None:
        return _signal(
            "database",
            "Database",
            "not_configured",
            "No PostgreSQL database is configured; in-memory repositories are in use.",
        )
    started = perf_counter()
    try:
        async with database.platform_transaction() as connection:
            await connection.execute("SELECT 1")
    except Exception:  # noqa: BLE001 - report a safe status, never the error text
        return _signal(
            "database", "Database", "attention", "The database check did not succeed."
        )
    latency = round((perf_counter() - started) * 1000, 1)
    return _signal(
        "database",
        "Database",
        "healthy",
        "PostgreSQL answered a trivial query.",
        {"latency_ms": latency},
    )


async def _queue_signal(state: Any) -> dict[str, Any]:
    repository = getattr(state, "post_call_job_repository", None)
    counter = getattr(repository, "count_jobs_by_state", None)
    if counter is None:
        return _signal(
            "post_call_queue",
            "Post-call jobs",
            "not_configured",
            "No post-call job repository is configured.",
        )
    result = counter()
    counts = await result if isawaitable(result) else result
    metrics = {name: int(counts.get(name, 0)) for name in JOB_STATES}
    if metrics["dead_letter"] > 0:
        return _signal(
            "post_call_queue",
            "Post-call jobs",
            "attention",
            "Some post-call jobs exhausted their retries and need review.",
            metrics,
        )
    return _signal(
        "post_call_queue",
        "Post-call jobs",
        "healthy",
        "No post-call jobs are in the dead-letter state.",
        metrics,
    )


async def _alerts_signal(state: Any) -> dict[str, Any]:
    service = getattr(state, "alert_service", None)
    if service is None:
        return _signal(
            "alerts", "Operational alerts", "not_configured", "Alerting is not running."
        )
    try:
        counts = await service.repository.count_open()
    except Exception:  # noqa: BLE001 - reported as attention, never raised
        return _signal(
            "alerts", "Operational alerts", "attention", "Open alerts could not be read."
        )
    serious = counts.get("error", 0) + counts.get("critical", 0)
    total = sum(counts.values())
    return _signal(
        "alerts",
        "Operational alerts",
        "attention" if serious else "healthy",
        f"{total} open alert(s); {serious} at error or critical severity."
        if total
        else "No open alerts.",
        {"open": total, "error_or_critical": serious},
    )


async def build_operations_snapshot(
    state: Any, studio_repository: Any
) -> dict[str, Any]:
    live_providers = _flag("RUN_LIVE_PROVIDERS")
    live_telephony = _flag("RUN_LIVE_TELEPHONY")
    outbound = getattr(state, "outbound_call_service", None) is not None
    active_sessions = await studio_repository.list_support_sessions(
        state="active", limit=100
    )
    signals = [
        _signal(
            "control_plane",
            "Control plane",
            "healthy",
            "The control plane is serving requests.",
        ),
        await _database_signal(state),
        _signal(
            "identity",
            "Identity verification",
            "healthy" if getattr(state, "oidc_provider", None) else "not_configured",
            "OIDC identity verification is configured."
            if getattr(state, "oidc_provider", None)
            else "No OIDC provider is configured; Studio sign-in cannot be verified.",
        ),
        await _queue_signal(state),
        _signal(
            "live_providers",
            "Live provider traffic",
            "healthy" if live_providers else "disabled",
            "Live provider traffic is enabled."
            if live_providers
            else "Live provider traffic is disabled in this environment.",
        ),
        _signal(
            "provider_health",
            "Provider health",
            "not_measured",
            "No live provider health probe runs from the control plane.",
        ),
        _signal(
            "telephony",
            "Live telephony",
            "healthy" if live_telephony else "disabled",
            (
                "Live telephony is enabled."
                if live_telephony
                else "Live telephony is disabled in this environment."
            )
            + (
                " Outbound runtime is configured."
                if outbound
                else " Outbound runtime is not configured."
            ),
        ),
        _signal(
            "carrier_health",
            "Carrier health",
            "not_measured",
            "No carrier health probe runs from the control plane.",
        ),
        await _alerts_signal(state),
        _signal(
            "support_sessions",
            "Support sessions",
            "healthy",
            "Active read-only support sessions.",
            {"active": len(active_sessions)},
        ),
    ]
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "environment": get_ucve_env(),
        "signals": signals,
    }
