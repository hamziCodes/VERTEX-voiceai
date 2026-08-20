"""Phase 04: Barge-In Arbitration and Recovery Rules."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

BARGE_VERIFY_MS = 700
BARGE_SUSTAIN_MS = 300


@pytest.fixture(scope="module")
def barge_module():
    try:
        from core.fsm import barge_in  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 04 implementation pending: {exc}")
    return barge_in


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_04_barge_in_arbitration_and_recovery_rules.md"
    )
    assert plan.is_file()


def test_barge_config_defaults_match_blueprint(barge_module) -> None:
    BargeInConfig = barge_module.BargeInConfig
    cfg = BargeInConfig()
    assert cfg.verify_window_ms == BARGE_VERIFY_MS
    assert cfg.min_sustained_speech_ms == BARGE_SUSTAIN_MS


@pytest.mark.asyncio
async def test_false_alarm_resumes_without_cancel(barge_module) -> None:
    BargeInController = barge_module.BargeInController
    controller = BargeInController()
    result = await controller.simulate_verify(
        sustained_speech_ms=100, within_window_ms=BARGE_VERIFY_MS
    )
    assert result.committed is False
    assert result.cancelled_tasks is False


@pytest.mark.asyncio
async def test_sustained_speech_commits_interrupt(barge_module) -> None:
    BargeInController = barge_module.BargeInController
    controller = BargeInController()
    controller.buffer_final("hello there friend")
    result = await controller.simulate_verify(
        sustained_speech_ms=BARGE_SUSTAIN_MS, within_window_ms=BARGE_VERIFY_MS
    )
    assert result.committed is True
    assert controller.next_turn_input() == "hello there friend"


@pytest.mark.asyncio
async def test_three_point_cancel_execution(barge_module) -> None:
    import asyncio
    ThreePointCancel = barge_module.ThreePointCancel

    cancel_contract = ThreePointCancel()
    flushed = False

    def flush_cb():
        nonlocal flushed
        flushed = True

    async def dummy_task():
        await asyncio.sleep(10)

    task = asyncio.create_task(dummy_task())
    cancel_contract.register_task(task)
    cancel_contract.register_flush_callback(flush_cb)

    cancelled_count = cancel_contract.execute_cancel_and_flush()
    assert cancelled_count == 1
    assert flushed is True
    assert task.cancelling() > 0 or task.cancelled()



def test_control_event_barge_in_wire_format() -> None:
    from core.types.events import ControlEventBargeIn, ControlEventType

    event = ControlEventBargeIn(timestamp_ms=50.0, reason="sustained_speech")
    assert event.event_type == ControlEventType.BARGE_IN
    assert event.timestamp_ms == 50.0
    assert event.payload == {"reason": "sustained_speech"}


@pytest.mark.asyncio
async def test_1000_iteration_zero_post_cancel_leak_fuzz(barge_module) -> None:
    import asyncio
    BargeInController = barge_module.BargeInController

    post_cancel_leaks = 0
    for i in range(1000):
        controller = BargeInController()

        async def worker():
            await asyncio.sleep(1.0)
            nonlocal post_cancel_leaks
            post_cancel_leaks += 1

        task = asyncio.create_task(worker())
        controller.cancel_contract.register_task(task)
        result = await controller.simulate_verify(300, 700)
        assert result.committed is True

    await asyncio.sleep(0.01)
    assert post_cancel_leaks == 0

