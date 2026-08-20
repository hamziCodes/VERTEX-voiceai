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


def test_full_turn_lifecycle_happy_path(fsm_module) -> None:
    SessionFSM = fsm_module.SessionFSM
    SessionState = fsm_module.SessionState

    fsm = SessionFSM()
    assert fsm.trigger("session_admitted") == SessionState.LISTENING
    assert fsm.trigger("vad_speech_start") == SessionState.USER_SPEAKING
    assert fsm.trigger("vad_speech_end") == SessionState.PROCESSING_INFERENCE
    assert fsm.context.turn_index == 1
    assert fsm.trigger("tool_call_start") == SessionState.TOOL_EXECUTING
    assert fsm.trigger("tool_result") == SessionState.PROCESSING_INFERENCE
    assert fsm.trigger("tts_first_byte") == SessionState.AGENT_SPEAKING
    assert fsm.trigger("tts_drained") == SessionState.LISTENING


def test_barge_in_verify_and_confirmation(fsm_module) -> None:
    SessionFSM = fsm_module.SessionFSM
    SessionState = fsm_module.SessionState

    fsm = SessionFSM()
    fsm.trigger("session_admitted")
    fsm.trigger("vad_speech_start")
    fsm.trigger("vad_speech_end")
    fsm.trigger("tts_first_byte")
    assert fsm.state == SessionState.AGENT_SPEAKING

    fsm.trigger("vad_speech_start")
    assert fsm.state == SessionState.BARGE_IN_VERIFY

    fsm.trigger("barge_confirmed")
    assert fsm.state == SessionState.BARGE_IN_INTERRUPTED

    fsm.trigger("vad_speech_end")
    assert fsm.state == SessionState.PROCESSING_INFERENCE
    assert fsm.context.turn_index == 2


def test_barge_in_false_alarm_recovery(fsm_module) -> None:
    SessionFSM = fsm_module.SessionFSM
    SessionState = fsm_module.SessionState

    fsm = SessionFSM(initial_state=SessionState.AGENT_SPEAKING)
    fsm.trigger("vad_speech_start")
    assert fsm.state == SessionState.BARGE_IN_VERIFY

    fsm.trigger("barge_false_alarm")
    assert fsm.state == SessionState.AGENT_SPEAKING


def test_disconnect_from_all_active_states(fsm_module) -> None:
    SessionFSM = fsm_module.SessionFSM
    SessionState = fsm_module.SessionState

    for state in SessionState:
        if state == SessionState.DISCONNECTED:
            continue
        fsm = SessionFSM(initial_state=state)
        assert fsm.can_transition("disconnect")
        assert fsm.trigger("disconnect") == SessionState.DISCONNECTED


def test_10k_triggers_performance(fsm_module) -> None:
    import time

    SessionFSM = fsm_module.SessionFSM

    start = time.perf_counter()
    for _ in range(2500):
        fsm = SessionFSM()
        fsm.trigger("session_admitted")
        fsm.trigger("vad_speech_start")
        fsm.trigger("vad_speech_end")
        fsm.trigger("disconnect")
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert elapsed_ms < 50.0  # Target < 50 ms total for 10,000 triggers

