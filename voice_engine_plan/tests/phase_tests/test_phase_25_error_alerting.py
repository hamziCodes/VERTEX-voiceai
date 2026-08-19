"""Phase 25: Error Taxonomy and Alerting Strategy."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_25_error_taxonomy_and_alerting_strategy.md"
)


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_generic_client_errors_and_dlq_retention() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "30 days" in text or "30-day" in text
    assert "generic" in text.lower()
    assert "email" in text.lower()
    assert "None — fully deterministic" in text


def test_client_mapper_strips_internals() -> None:
    try:
        from core.errors.client_mapper import ClientErrorMapper  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 25 implementation pending: {exc}")
    mapped = ClientErrorMapper.to_client_message("INTERNAL_ERROR", details={"stack": "secret"})
    assert "stack" not in mapped.lower()
