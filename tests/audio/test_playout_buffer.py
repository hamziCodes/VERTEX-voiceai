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
