import sys
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from backend.app.orchestration.session import SessionOrchestrator
from backend.app.transport.audio_sender import AudioSender
from backend.app.core.state_machine import CallState

async def test_verification_window_false_alarm():
    print("\n--- Running Test: False Alarm Resumption ---")
    mock_ws = AsyncMock()
    ws_lock = asyncio.Lock()
    audio_sender = AudioSender("test-verify", ws_lock)
    mock_receiver = MagicMock()
    
    orchestrator = SessionOrchestrator(
        session_id="test-verify",
        websocket=mock_ws,
        audio_receiver=mock_receiver,
        audio_sender=audio_sender,
        ws_lock=ws_lock
    )
    
    # Setup state
    orchestrator._state_manager.transition_to(CallState.SPEAKING)
    # Simulate active playout
    audio_sender.speaking_until = time.time() + 10.0 
    
    # 1. Trigger speech start
    print("Triggering user speech start (e.g. ambient fan hum / click)")
    await orchestrator._on_speech_start()
    
    # AudioSender should be paused immediately
    assert audio_sender.paused is True, "AudioSender should be paused during validation window"
    assert orchestrator._in_verification_window is True, "Verification window should be active"
    
    # 2. Simulate very brief noise ending after 100ms
    await asyncio.sleep(0.1)
    print("Noise ends after 100ms")
    await orchestrator._on_speech_end()
    
    # Let's mock VAD is_speech_active to return False (it ended)
    orchestrator._vad = MagicMock()
    type(orchestrator._vad).is_speech_active = PropertyMock = MagicMock(return_value=False)
    
    # 3. Wait for validation window (700ms) to complete - sleep 0.9s to be safe from scheduler race conditions
    print("Waiting for validation window to elapse (sleeping 0.9s)...")
    await asyncio.sleep(0.9)
    
    # Verify: False Alarm -> Playout Resumed
    assert audio_sender.paused is False, "AudioSender should be resumed after false alarm"
    assert orchestrator._in_verification_window is False, "Verification window should have exited"
    print("🎉 False Alarm Resumption test PASSED!")


async def test_verification_window_true_barge_in():
    print("\n--- Running Test: True Barge-in Confirmation ---")
    mock_ws = AsyncMock()
    ws_lock = asyncio.Lock()
    audio_sender = AudioSender("test-verify-true", ws_lock)
    mock_receiver = MagicMock()
    
    orchestrator = SessionOrchestrator(
        session_id="test-verify-true",
        websocket=mock_ws,
        audio_receiver=mock_receiver,
        audio_sender=audio_sender,
        ws_lock=ws_lock
    )
    
    # Setup mock barge_in method
    orchestrator._barge_in = AsyncMock()
    
    orchestrator._state_manager.transition_to(CallState.SPEAKING)
    audio_sender.speaking_until = time.time() + 10.0
    
    # 1. Trigger speech start
    print("Triggering actual user speech onset")
    await orchestrator._on_speech_start()
    
    # AudioSender should be paused immediately
    assert audio_sender.paused is True, "AudioSender should be paused during validation window"
    
    # Mock VAD is_speech_active to return True (user is still speaking after 700ms)
    orchestrator._vad = MagicMock()
    type(orchestrator._vad).is_speech_active = PropertyMock = MagicMock(return_value=True)
    
    # 2. Wait for validation window (700ms) to complete - sleep 0.9s to prevent scheduler race conditions
    print("Waiting for validation window to elapse (sleeping 0.9s)...")
    await asyncio.sleep(0.9)
    
    # Verify: True Barge-in -> Cancel tasks & call _barge_in
    assert audio_sender.paused is False, "AudioSender should be unpaused/resumed before barge_in processing"
    orchestrator._barge_in.assert_called_once()
    assert orchestrator._in_verification_window is False, "Verification window should have exited"
    print("🎉 True Barge-in test PASSED!")


async def main():
    try:
        await test_verification_window_false_alarm()
        await test_verification_window_true_barge_in()
        print("\nAll Barge-in Verification tests PASSED!")
    except AssertionError as e:
        print(f"\n❌ Test Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
