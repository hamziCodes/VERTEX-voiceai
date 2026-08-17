import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio
import time
import json
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from backend.app.services.llm.groq_service import GroqService

load_dotenv()

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
    
    if not os.getenv("GROQ_API_KEY"):
        print("❌ Error: GROQ_API_KEY missing from .env file.")
        return

    print("=== 🚀 Starting Automated Stress Tests ===\n")
    from backend.app.core.config.language_registry import LanguageRegistry
    registry = LanguageRegistry()
    service = GroqService(session_id="audit-session-002")
    service.on_sentence(mock_tts_callback)

    # Load test scenarios from JSON
    scenarios_path = Path(__file__).parent / "groq_test_scenarios.json"
    with open(scenarios_path, "r", encoding="utf-8") as file:
        scenarios = json.load(file)

    for index, test in enumerate(scenarios, 1):
        print(f"🧪 Test {index}: {test['scenario_name']}")
        print(f"  👤 [Customer]: {test['input_text']}")
        
        first_chunk_received = False
        start_time = time.time()
        
        lang_profile = registry.get("ur")
        await service.generate_reply(test['input_text'], lang_profile)
        print("-" * 60)
        
        # Small delay between tests to ensure clean log separation
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_audit())