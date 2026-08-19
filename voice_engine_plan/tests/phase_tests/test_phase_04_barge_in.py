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
