import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

load_dotenv(project_root / ".env")

from backend.app.services.tts.google_service import GoogleTTSService

async def test_tts():
    service = GoogleTTSService()
    print("Testing English TTS...")
    async def get_en_text():
        yield "Hello, how are you?"
    
    try:
        async for chunk in service.stream_audio(get_en_text(), "en"):
            print(f"Received English audio chunk of size {len(chunk)} bytes")
            break
    except Exception as e:
        print(f"English error: {e}")
        
    print("\nTesting Arabic TTS with mixed text...")
    async def get_ar_text():
        yield "أفادنا أن لدينا جهاز كمبيوتر مخمول من ماركة HP، يحتوي على محرك ثماني النواة وذاكرة 8 جيجابايت."
        yield "أتريد أن أقوم بتسليمه لك؟"
        
    try:
        async for chunk in service.stream_audio(get_ar_text(), "ar"):
            print(f"Received Arabic audio chunk of size {len(chunk)} bytes")
    except Exception as e:
        print(f"Arabic error: {e}")

    await service.aclose()

if __name__ == "__main__":
    asyncio.run(test_tts())
