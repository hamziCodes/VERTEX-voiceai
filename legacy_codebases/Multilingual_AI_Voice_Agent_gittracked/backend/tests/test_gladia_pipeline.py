import asyncio
import logging
import wave
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.app.transport.audio_receiver import AudioReceiver
from backend.app.services.stt.gladia_service import GladiaService
from backend.app.core.interfaces import Transcript

# Setup basic logging to see our outputs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

GLADIA_API_KEY = os.getenv("GLADIA_API_KEY")
if not GLADIA_API_KEY:
    raise ValueError("GLADIA_API_KEY not found in environment variables or .env file.")

TEST_AUDIO_FILE = SCRIPT_DIR / "minglish_test.wav" # You need a raw 16kHz, 16-bit Mono WAV file

async def mock_flutter_client(receiver: AudioReceiver):
    """Simulates the Flutter frontend streaming raw PCM chunks over a WebSocket."""
    logger.info("Mock Client: Opening WAV file...")
    try:
        with wave.open(str(TEST_AUDIO_FILE), 'rb') as wf:
            # Verify hardware specs match our config
            assert wf.getframerate() == 16000, "Audio must be 16kHz"
            assert wf.getsampwidth() == 2, "Audio must be 16-bit"
            assert wf.getnchannels() == 1, "Audio must be Mono"

            # Read exactly 20ms of audio at a time (320 bytes for 16kHz 16-bit mono)
            chunk_size = int(16000 * 0.02 * 2) 
            
            while True:
                data = wf.readframes(chunk_size // 2)
                if not data:
                    break
                
                # Push into our Phase 1 buffer
                await receiver.enqueue_chunk(data)
                
                # Sleep to simulate real-time streaming speed
                await asyncio.sleep(0.02)
                
                # EDGE CASE TEST: Uncomment to simulate a 1-second network lag spike
                # if random.random() > 0.95:
                #     logger.warning("Mock Client: Simulating network lag...")
                #     await asyncio.sleep(1.0)
                
    except FileNotFoundError:
        logger.error(f"Please create a test WAV first: {TEST_AUDIO_FILE}")
    
    logger.info("Mock Client: Finished streaming audio.")

async def mock_llm_callback(transcript: Transcript):
    """Simulates Phase 3 receiving the text."""
    language = (transcript.language or "unknown").upper()
    if transcript.is_final:
        print(f"\n[FINAL TO LLM] {language}: {transcript.text}\n")
    else:
        print(f"[Interim]: {transcript.text}", end="\r")

async def main():
    session_id = "test-session-001"
    
    # 1. Initialize Phase 1 Buffer
    receiver = AudioReceiver(session_id)
    
    # 2. Initialize Phase 2 Service
    stt_service = GladiaService(session_id, receiver, api_key=GLADIA_API_KEY)
    
    # 3. Attach our mock Phase 3 callback
    stt_service.on_transcript(mock_llm_callback)
    
    # 4. Start the STT service (Runs in background)
    stt_task = asyncio.create_task(stt_service.start())
    
    # 5. Start the mock audio stream
    await mock_flutter_client(receiver)
    
    # Give it 2 seconds to process the final chunks, then gracefully shutdown
    await asyncio.sleep(2)
    await stt_service.stop_recording()
    await stt_task # Ensure the service task is awaited to prevent unhandled exceptions

if __name__ == "__main__":
    asyncio.run(main())
