import sys
import os
import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from backend.app.services.uplift_service import UpliftTTSService



async def mock_gemini_stream():
    # Only 39 total characters to save API credits
    sentences = [
        "یہ نیا laptop ہے۔",       # Cold start: Tests TTFB
        "اس کا motherboard تیز ہے۔" # Warm start: Tests pooling and Minglish
    ]
    for s in sentences:
        yield s
        await asyncio.sleep(0.1) # Micro-delay simulating LLM generation

async def run_tts_test() -> None:
    if not os.getenv("UPLIFT_API_KEY"):
        print("❌ Error: UPLIFT_API_KEY missing from .env file.")
        return

    print("=== 🚀 Starting Ultra-Lean Uplift TTS Test ===\n")
    service = UpliftTTSService()
    
    start_time = time.time()
    sentence_count = 1
    chunk_count = 0
    total_bytes = 0
    
    try:
        # Saving output to verify the WAV header stripper worked
        with open("test_output.raw", "wb") as f:
            async for chunk in service.stream_audio(mock_gemini_stream()):
                chunk_count += 1
                total_bytes += len(chunk)
                
                # Log the TTFB for the very first chunk to see your latency
                if chunk_count == 1:
                    elapsed = time.time() - start_time
                    print(f"⏱️ Time to First Audio Byte (Cold Start): {elapsed:.3f}s")
                
                f.write(chunk)
                
        print(f"\n✅ Success! Received {total_bytes} bytes of raw audio.")
        print("💾 Saved as 'test_output.raw'. Import into Audacity (22050Hz, 32-bit float) to listen.")
        
    except Exception as e:
        print(f"❌ Pipeline Failed: {e}")
    finally:
        await service.aclose()

if __name__ == "__main__":
    asyncio.run(run_tts_test())