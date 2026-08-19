"""Phase 19: Telephony Abstraction."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_19_telephony_abstraction_and_secondary_trunk_readiness.md"
    )
    assert plan.is_file()


def test_two_trunk_config_required() -> None:
    try:
        from telephony_gateway.trunk_config import validate_trunk_chain  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 19 implementation pending: {exc}")
    with pytest.raises(ValueError):
        validate_trunk_chain([{"provider": "telnyx", "role": "primary"}])
