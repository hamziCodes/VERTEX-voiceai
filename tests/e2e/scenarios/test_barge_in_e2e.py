from __future__ import annotations

import pytest
from core.fsm.session_fsm import SessionFSM, SessionState
from core.fsm.barge_in import BargeInController


@pytest.mark.asyncio
async def test_barge_in_mid_tts_cancels_and_transitions() -> None:
    fsm = SessionFSM()
    assert fsm.state == SessionState.CONNECTING

    fsm.trigger("session_admitted")
    assert fsm.state == SessionState.LISTENING

    fsm.trigger("vad_speech_start")
    fsm.trigger("vad_speech_end")
    fsm.trigger("tts_first_byte")
    assert fsm.state == SessionState.AGENT_SPEAKING

    # Speech detected during TTS triggers verification
    fsm.trigger("vad_speech_start")
    assert fsm.state == SessionState.BARGE_IN_VERIFY

    # Barge confirmed cancels TTS and transitions
    fsm.trigger("barge_confirmed")
    assert fsm.state == SessionState.BARGE_IN_INTERRUPTED

    # Test barge in controller arbitration
    barge = BargeInController()
    barge.buffer_final("Excuse me")
    result = await barge.simulate_verify(sustained_speech_ms=300, within_window_ms=700)
    assert result.committed is True
    assert result.cancelled_tasks is True
    assert result.flushed_outbound is True


