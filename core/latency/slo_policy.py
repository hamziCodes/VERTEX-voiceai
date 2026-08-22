"""Tenant SLOPolicy Data Model — Warn-only v1 policy with opt-in demotion."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SLOPolicy(BaseModel):
    """Tenant-specific latency Service Level Objective policy."""

    e2e_p50_target_ms: float = Field(default=450.0, description="Target p50 end-to-end latency in ms")
    e2e_p95_target_ms: float = Field(default=850.0, description="Target p95 end-to-end latency in ms")
    enforce_demotion: bool = Field(default=False, description="Global default false (warn-only v1)")
    alert_on_breach: bool = Field(default=True, description="Emit warning metrics/logs on breach")
