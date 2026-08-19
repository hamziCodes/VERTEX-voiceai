"""Phase 07: Observability Foundations."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def observability_module():
    try:
        from core import observability  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 07 implementation pending: {exc}")
    return observability


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_07_observability_foundations.md"
    )
    assert plan.is_file()


def test_context_binds_call_id(observability_module) -> None:
    ctx = observability_module.context
    ctx.bind(call_id="call-123", tenant_id="tenant-456")
    bound = ctx.get()
    assert bound["call_id"] == "call-123"
    assert bound["tenant_id"] == "tenant-456"
    ctx.clear()


def test_phi_redaction_strips_phone(observability_module) -> None:
    redact = observability_module.logging.redact_phi
    text = "Call me at 555-123-4567 please"
    cleaned = redact(text)
    assert "555-123-4567" not in cleaned


def test_auth_query_params_redacted(observability_module) -> None:
    redact_url = observability_module.logging.redact_url_params
    url = "wss://voice.example.com/ws?token=secret-jwt&session_id=abc"
    cleaned = redact_url(url)
    assert "secret-jwt" not in cleaned
    assert "token=" in cleaned or "[REDACTED]" in cleaned
