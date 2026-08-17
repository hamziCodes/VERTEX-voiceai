import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

load_dotenv(project_root / ".env")

from backend.app.orchestration.session import SessionOrchestrator
from backend.app.core.config.language_registry import LanguageRegistry, LanguageProfile
from backend.app.core.state_machine import CallState
from backend.app.transport.audio_sender import AudioSender

async def test_orchestrator_arabic():
    # Mock WebSocket
    mock_ws = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.send_bytes = AsyncMock()
    
    # Lock
    ws_lock = asyncio.Lock()
    
    # Audio Receiver and Sender
    mock_receiver = MagicMock()
    audio_sender = AudioSender("test-session", ws_lock)
    
    # Register mock websocket in connection manager
    from backend.app.transport.connection_manager import connection_manager
    connection_manager.active_connections["test-session"] = mock_ws
    
    # Orchestrator
    orchestrator = SessionOrchestrator(
        session_id="test-session",
        websocket=mock_ws,
        audio_receiver=mock_receiver,
        audio_sender=audio_sender,
        ws_lock=ws_lock
    )
    
    # Let's get Arabic profile
    registry = LanguageRegistry()
    ar_profile = registry.get("ar")
    print(f"Loaded Profile: {ar_profile.name}, TTS: {ar_profile.tts_provider}")
    
    # Let's run a turn with Arabic text
    user_text = "أريد شراء جهاز كومبيوتر محمولا"
    print("Running turn...")
    
    # Start the sender loop in background so we don't block
    sender_task = asyncio.create_task(audio_sender.send_loop())
    
    orchestrator._state_manager.transition_to(CallState.THINKING)
    await orchestrator._run_turn(user_text, ar_profile)
    
    # Let's wait a bit for any pending tasks to complete
    await asyncio.sleep(2)
    
    # Stop the sender loop
    audio_sender.stop()
    sender_task.cancel()
    
    # Check what was sent to WebSocket
    print("\n--- WS Sent Texts ---")
    for call in mock_ws.send_text.call_args_list:
        print(call[0][0])
        
    print("\n--- WS Sent Bytes Count ---")
    print(f"Number of audio chunks sent: {mock_ws.send_bytes.call_count}")
    
    total_bytes = sum(len(call[0][0]) for call in mock_ws.send_bytes.call_args_list)
    print(f"Total audio bytes sent: {total_bytes}")
    
    await orchestrator.shutdown()

if __name__ == "__main__":
    asyncio.run(test_orchestrator_arabic())
