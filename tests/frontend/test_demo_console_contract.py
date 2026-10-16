"""Static interaction/layout contract for the dependency-free demo console."""

from __future__ import annotations

from pathlib import Path

DEMO = Path("examples/web-client/index.html")


def _html() -> str:
    return DEMO.read_text(encoding="utf-8")


def test_playground_has_compact_workspace_and_panel_tabs() -> None:
    html = _html()

    assert 'class="playground-workspace"' in html
    assert 'data-panel="latency"' in html
    assert 'data-panel="metrics"' in html
    assert 'data-panel="events"' in html
    assert 'id="panel-latency"' in html
    assert 'id="panel-metrics"' in html
    assert 'id="panel-events"' in html


def test_demo_displays_truthful_runtime_and_stt_modes() -> None:
    html = _html()

    assert 'id="runtimeModeBadge"' in html
    assert 'id="sttModeNotice"' in html
    assert "p.kind === 'session_ready'" in html
    assert "p.kind === 'vad_debug'" in html


def test_playground_uses_internal_scroll_at_desktop_height() -> None:
    html = _html()

    assert "height: calc(100vh - var(--header-height))" in html
    assert ".workspace-panel" in html
    assert "overflow-y: auto" in html
