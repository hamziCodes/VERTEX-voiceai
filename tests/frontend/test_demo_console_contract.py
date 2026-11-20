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


def test_knowledge_setup_has_complete_operator_workflow() -> None:
    html = _html()

    assert 'data-tab="knowledge"' in html
    assert 'id="tab-knowledge"' in html
    assert 'id="knowledgeConnectBtn"' in html
    assert 'id="knowledgeBaseSelect"' in html
    assert 'id="knowledgeCreateForm"' in html
    assert 'id="knowledgeUploadForm"' in html
    assert 'accept=".pdf,.docx,.txt,.md,.csv,.xlsx"' in html
    assert 'id="knowledgeFaqForm"' in html
    assert 'id="knowledgePreviewForm"' in html
    assert 'id="knowledgeActivateBtn"' in html
    assert 'id="knowledgeBindBtn"' in html
    assert 'id="knowledgeSourceList"' in html
    assert 'aria-live="polite"' in html


def test_knowledge_setup_calls_real_api_without_persisting_management_key() -> None:
    html = _html()

    assert "/v1/knowledge-bases" in html
    assert "/preview-query" in html
    assert "/sources/" in html
    assert "localStorage" not in html
    assert "sessionStorage" not in html
    assert "OFFLINE SAMPLE RESULT" not in html


def test_knowledge_setup_has_bounded_desktop_and_mobile_layouts() -> None:
    html = _html()

    assert ".knowledge-workspace" in html
    assert ".knowledge-task-tabs" in html
    assert "#tab-knowledge.active" in html
    assert "knowledge-workspace { grid-template-columns: 1fr;" in html
