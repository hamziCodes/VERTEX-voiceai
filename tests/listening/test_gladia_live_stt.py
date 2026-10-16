"""Unit tests for ``core.providers.adapters.gladia_live_stt.GladiaLiveSTTSession``."""

from __future__ import annotations

import asyncio
import json

import pytest

from core.providers.adapters.gladia_live_stt import GladiaLiveSTTSession
from core.providers.interfaces.stt import Transcript


@pytest.mark.asyncio
async def test_mock_mode_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLATFORM_GLADIA_API_KEY", raising=False)
    monkeypatch.delenv("GLADIA_API_KEY", raising=False)
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")

    session = GladiaLiveSTTSession(api_key="")
    started = await session.start()

    assert started is False
    assert session.is_live is False


@pytest.mark.asyncio
async def test_mock_mode_when_run_live_providers_not_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_GLADIA_API_KEY", "test-key-should-not-connect")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)

    session = GladiaLiveSTTSession()
    started = await session.start()

    assert started is False
    assert session.is_live is False


def test_parse_message_transcript_json() -> None:
    session = GladiaLiveSTTSession(api_key="unit-test-key", language="en")
    payload = {
        "type": "transcript",
        "data": {
            "is_final": True,
            "utterance": {
                "text": "hello there",
                "confidence": 0.92,
            },
        },
    }

    transcript = session._parse_message(json.dumps(payload))

    assert transcript is not None
    assert transcript.text == "hello there"
    assert transcript.is_final is True
    assert transcript.confidence == 0.92
    assert transcript.language == "en"


def test_parse_message_ignores_non_transcript() -> None:
    session = GladiaLiveSTTSession(api_key="unit-test-key")
    payload = {"type": "session_started", "data": {}}

    assert session._parse_message(json.dumps(payload)) is None


@pytest.mark.asyncio
async def test_connect_factory_injected_without_live_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """connect_factory is injectable; mock mode still skips live init."""
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")

    async def fake_connect(url: str) -> object:
        raise AssertionError(f"connect should not be called in mock mode: {url}")

    session = GladiaLiveSTTSession(
        api_key="test-key",
        connect_factory=fake_connect,
    )
    started = await session.start()

    assert started is False
    assert session.is_live is False

    # Parsing works independently of connect/start.
    raw = json.dumps(
        {
            "type": "transcript",
            "data": {
                "is_final": False,
                "utterance": {"text": "partial hello"},
            },
        }
    )
    partial = session._parse_message(raw)
    assert partial is not None
    assert partial.text == "partial hello"
    assert partial.is_final is False


@pytest.mark.asyncio
async def test_transcript_queue_is_bounded_and_never_drops_finals() -> None:
    session = GladiaLiveSTTSession(api_key="unit-test-key")
    partial = Transcript(text="partial", is_final=False)
    for _ in range(session.transcript_queue_capacity):
        await session._queue_transcript(partial)

    await session._queue_transcript(partial)
    assert session.dropped_partial_count == 1

    final = Transcript(text="final", is_final=True)
    pending_final = asyncio.create_task(session._queue_transcript(final))
    await asyncio.sleep(0)
    assert pending_final.done() is False

    session._transcript_q.get_nowait()
    await pending_final
    assert session.dropped_final_count == 0
