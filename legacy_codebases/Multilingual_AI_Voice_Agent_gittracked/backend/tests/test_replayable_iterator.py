import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from backend.app.services.tts.tts_manager import ReplayableAsyncIterator

async def mock_generator():
    yield "Hello"
    yield "World"

class MockIterableBridge:
    def __aiter__(self):
        return mock_generator()

async def test_replayable():
    # 1. Test wrapping direct generator (iterator)
    gen = mock_generator()
    replay_iter = ReplayableAsyncIterator(gen)
    
    results1 = []
    async for val in replay_iter:
        results1.append(val)
    assert results1 == ["Hello", "World"], f"Expected ['Hello', 'World'], got {results1}"
    
    replay_iter.enable_replay()
    results2 = []
    async for val in replay_iter:
        results2.append(val)
    assert results2 == ["Hello", "World"], f"Expected ['Hello', 'World'], got {results2}"

    # 2. Test wrapping MockIterableBridge (iterable only, like _SentenceBridge)
    bridge = MockIterableBridge()
    replay_iter_bridge = ReplayableAsyncIterator(bridge)
    
    results_bridge_1 = []
    async for val in replay_iter_bridge:
        results_bridge_1.append(val)
    assert results_bridge_1 == ["Hello", "World"], f"Expected ['Hello', 'World'], got {results_bridge_1}"
    
    replay_iter_bridge.enable_replay()
    results_bridge_2 = []
    async for val in replay_iter_bridge:
        results_bridge_2.append(val)
    assert results_bridge_2 == ["Hello", "World"], f"Expected ['Hello', 'World'], got {results_bridge_2}"
    
    print("🎉 ReplayableAsyncIterator test with iterables and iterators PASSED!")

if __name__ == "__main__":
    asyncio.run(test_replayable())
