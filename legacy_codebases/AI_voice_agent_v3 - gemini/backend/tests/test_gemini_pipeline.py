import sys
import os
import asyncio
import time
import json
from pathlib import Path
from dotenv import load_dotenv

# Ensure stdout handles UTF-8 (especially for Urdu and emoji printing on Windows)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from backend.app.services.gemini_service import GeminiService

load_dotenv()

# Global variables for callback tracking
start_time = 0.0
first_chunk_received = False

async def mock_tts_callback(sentence: str) -> None:
    global start_time, first_chunk_received
    
    current_time = time.time()
    elapsed = current_time - start_time
    
    if not first_chunk_received:
        print(f"  ⏱️  Time to First Sentence: {elapsed:.3f}s")
        first_chunk_received = True
        
    print(f"  🔊 [TTS]: {sentence}")

async def run_audit() -> None:
    global start_time, first_chunk_received
    
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY missing from .env file.")
        return

    print("=== 🚀 Starting Automated Gemini Stress Tests ===\n")
    service = GeminiService(session_id="audit-session-gemini-002")
    service.on_sentence(mock_tts_callback)

    # Load test scenarios from JSON
    scenarios_path = Path(__file__).parent / "gemini_test_scenarios.json"
    with open(scenarios_path, "r", encoding="utf-8") as file:
        scenarios = json.load(file)

    for index, test in enumerate(scenarios, 1):
        print(f"🧪 Test {index}: {test['scenario_name']}")
        print(f"  👤 [Customer]: {test['input_text']}")
        
        first_chunk_received = False
        start_time = time.time()
        
        await service.generate_reply(test['input_text'])
        print("-" * 60)
        
        # Delay to prevent hitting Gemini Free Tier rate limits (5 RPM)
        if index < len(scenarios):
            print("⏱️ Sleeping 12 seconds to respect Gemini Free Tier rate limits (5 RPM)...")
            await asyncio.sleep(12)

if __name__ == "__main__":
    asyncio.run(run_audit())
