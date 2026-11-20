"""Provider runtime-mode status exposed to the browser console."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.providers import mode
from core.types.events import ControlEventType
from worker_raw.orchestration.pipeline import PipelineOrchestrator


def _runtime_status() -> dict[str, str]:
    assert hasattr(mode, "provider_runtime_status")
    return mode.provider_runtime_status()


def test_explicit_mock_mode_reports_disabled_mock_transcript(monkeypatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "development")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    monkeypatch.delenv("UCVE_STT_MOCK_TEXT", raising=False)

    assert _runtime_status() == {
        "provider_mode": "mock",
        "stt_transcript_mode": "disabled",
    }


def test_mock_mode_reports_fixed_transcript_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    monkeypatch.setenv("UCVE_STT_MOCK_TEXT", "Offline speech detected")

    assert _runtime_status()["stt_transcript_mode"] == "fixed_mock"


def test_explicit_live_mode_reports_live_transcript(monkeypatch) -> None:
    monkeypatch.delenv("RUN_MOCK_PROVIDERS", raising=False)
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "1")

    assert _runtime_status() == {
        "provider_mode": "live",
        "stt_transcript_mode": "live",
    }


@pytest.mark.asyncio
async def test_vad_state_transition_is_emitted_without_debug_mode(monkeypatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.delenv("UCVE_DEBUG_LISTENING", raising=False)
    sent: list[tuple[object, dict[str, object]]] = []

    class Transport:
        async def send_control_event(
            self, event_type: object, payload: dict[str, object]
        ) -> None:
            sent.append((event_type, payload))

    orchestrator = PipelineOrchestrator()
    orchestrator._ws_session = SimpleNamespace(transport=Transport())

    await orchestrator._emit_vad_state(speaking=True, probability=0.87)

    assert sent == [
        (
            ControlEventType.METRIC,
            {"kind": "vad_state", "speech": True, "probability": 0.87},
        )
    ]
