"""Phase 14: Usage Metering and Tenant Quotas."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def metering_module():
    from core import metering  # type: ignore
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


@pytest.mark.asyncio
async def test_soft_cap_warn_at_80_percent(metering_module) -> None:
    QuotaEnforcer = metering_module.QuotaEnforcer
    limits = metering_module.QuotaLimits(max_minutes_month=100, soft_cap_percent=80, hard_cap_percent=100)
    enforcer = QuotaEnforcer(limits=limits)

    res = await enforcer.check_mint("t1", current_concurrent=1, current_monthly_minutes=85.0)
    assert res.allowed is True
    assert res.is_soft_cap_warn is True


@pytest.mark.asyncio
async def test_hard_cap_blocks_mint_at_100_percent(metering_module) -> None:
    QuotaEnforcer = metering_module.QuotaEnforcer
    limits = metering_module.QuotaLimits(max_minutes_month=100, hard_cap_percent=100)
    enforcer = QuotaEnforcer(limits=limits)

    res = await enforcer.check_mint("t1", current_concurrent=1, current_monthly_minutes=100.0)
    assert res.allowed is False
    assert "Monthly usage hard cap" in res.reason


def test_stale_heartbeat_sweeper_releases_slot_at_2_min(metering_module) -> None:
    import time
    tracker = metering_module.HeartbeatTracker(stale_timeout_sec=1)
    tracker._heartbeats["sess-active"] = time.time()
    tracker._heartbeats["sess-stale"] = time.time() - 2.0  # 2s old (>1s timeout)

    swept = tracker.sweep_stale_sessions()
    assert len(swept) == 1
    assert swept[0] == "sess-stale"


def test_sandbox_test_call_kind_skipped(metering_module) -> None:
    meter = metering_module.UsageMeter()
    written = meter.record("t1", "s1", metering_module.TEST_CALL_SEC, 60.0)
    assert written is True
    assert meter._events_log[-1]["is_sandbox"] is True


def test_tenant_a_usage_query_isolation() -> None:
    from control_plane.routes.usage import handle_get_usage

    status, body = handle_get_usage(tenant_id="tenant-a", requester_tenant_id="tenant-b")
    assert status == 403
    assert "forbidden" in body["error"]

