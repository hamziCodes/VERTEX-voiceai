"""UCVE Control-Plane Tenant Usage Query Route Handler."""

from __future__ import annotations

from typing import Any


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
