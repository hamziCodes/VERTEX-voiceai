from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_browser_playout_uses_configurable_prebuffer_and_reports_underruns() -> None:
    browser = (REPO_ROOT / "examples" / "web-client" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "clientPrebufferMs" in browser
    assert "playbackUnderrunCount" in browser
    assert "prebuffer_ms: delayMs" in browser
    assert "underrun: underrun" in browser


def test_browser_clears_scheduled_audio_and_reports_drain_boundaries() -> None:
    browser = (REPO_ROOT / "examples" / "web-client" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "type === 'control.clear_audio'" in browser
    assert "event_type: 'control.clear_audio_ack'" in browser
    assert "event_type: 'control.playback_drained'" in browser
    assert "played_audio_ms: stopped.playedAudioMs" in browser
    assert "playbackEndReceived" in browser
