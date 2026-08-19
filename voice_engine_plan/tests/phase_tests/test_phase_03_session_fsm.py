"""Phase 03: Core Session FSM and Turn Lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def fsm_module():
    try:
        from core.fsm import session_fsm  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 03 implementation pending: {exc}")
    return session_fsm


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_03_core_session_fsm_and_turn_lifecycle.md"
    )
    assert plan.is_file()


def test_happy_path_listening_to_user_speaking(fsm_module) -> None:
    SessionFSM = fsm_module.SessionFSM
    SessionState = fsm_module.SessionState

    fsm = SessionFSM()
    assert fsm.state == SessionState.CONNECTING
    fsm.trigger("session_admitted")
    assert fsm.state == SessionState.LISTENING
    fsm.trigger("vad_speech_start")
    assert fsm.state == SessionState.USER_SPEAKING


def test_illegal_transition_raises(fsm_module) -> None:
    SessionFSM = fsm_module.SessionFSM
    InvalidStateTransitionError = fsm_module.InvalidStateTransitionError

    fsm = SessionFSM()
    with pytest.raises(InvalidStateTransitionError):
        fsm.trigger("tts_first_byte")  # illegal from CONNECTING
