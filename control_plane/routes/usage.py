"""UCVE Control-Plane Tenant Usage Query Route Handler."""

from __future__ import annotations

from typing import Any

from core.db.repos.usage_pg import build_usage_repository


def handle_get_usage(
    tenant_id: str, requester_tenant_id: str
) -> tuple[int, dict[str, Any]]:
    """GET /v1/usage — Tenant-scoped usage and quota status query endpoint."""
    if not requester_tenant_id or tenant_id != requester_tenant_id:
        return 403, {"error": "Cross-tenant usage query forbidden."}

    return 200, {
        "status": "success",
        "tenant_id": tenant_id,
        "quota": {
            "max_concurrent": 10,
            "max_minutes_month": 1000,
            "current_concurrent": 0,
            "current_monthly_minutes": 0.0,
        },
        "totals": {
            "stt_sec": 0.0,
            "tts_sec": 0.0,
            "llm_tokens": 0.0,
            "agent_sec": 0.0,
        },
    }


async def query_usage(
    tenant_id: str,
    requester_tenant_id: str,
    *,
    repository: Any | None = None,
    admission: Any | None = None,
) -> tuple[int, dict[str, Any]]:
    """Return durable monthly totals and the active Redis lease count."""
    if not requester_tenant_id or tenant_id != requester_tenant_id:
        return 403, {"error": "Cross-tenant usage query forbidden."}
    usage_repository = (
        repository if repository is not None else build_usage_repository()
    )
    if usage_repository is None:
        return handle_get_usage(tenant_id, requester_tenant_id)
    snapshot = await usage_repository.get_usage_snapshot(tenant_id)
    current_concurrent = (
        await admission.current_tenant_count(tenant_id) if admission is not None else 0
    )
    totals = {
        "stt_sec": 0.0,
        "tts_sec": 0.0,
        "llm_tokens": 0.0,
        "agent_sec": 0.0,
        "telephony_sec": 0.0,
        **snapshot.totals,
    }
    return 200, {
        "status": "success",
        "tenant_id": tenant_id,
        "quota": {
            "max_concurrent": snapshot.max_concurrent,
            "max_minutes_month": snapshot.monthly_seconds_limit / 60.0,
            "max_llm_tokens_month": snapshot.max_llm_tokens_month,
            "current_concurrent": current_concurrent,
            "current_monthly_minutes": snapshot.monthly_seconds_used / 60.0,
            "current_monthly_llm_tokens": snapshot.monthly_llm_tokens,
            "soft_cap_percent": snapshot.soft_cap_percent,
            "hard_cap_percent": snapshot.hard_cap_percent,
        },
        "totals": totals,
    }
