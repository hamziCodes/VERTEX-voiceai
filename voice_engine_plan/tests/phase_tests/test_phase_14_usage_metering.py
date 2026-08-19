"""Phase 14: Usage Metering and Tenant Quotas."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def metering_module():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    try:
        from core import metering  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 14 implementation pending: {exc}")
    return metering


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_14_usage_metering_and_tenant_quotas.md"
    )
    assert plan.is_file()


def test_zero_quantity_skipped(metering_module) -> None:
    UsageMeter = metering_module.UsageMeter
    meter = UsageMeter()
    written = meter.record_many(
        tenant_id="t1",
        session_id="s1",
        items={"stt_sec": 0, "tts_sec": 1.5},
    )
    assert written == 1


@pytest.mark.asyncio
async def test_concurrent_quota_blocks_mint(metering_module) -> None:
    QuotaEnforcer = metering_module.QuotaEnforcer
    enforcer = QuotaEnforcer(max_concurrent=0)
    result = await enforcer.check_mint("tenant-at-cap")
    assert result.allowed is False
