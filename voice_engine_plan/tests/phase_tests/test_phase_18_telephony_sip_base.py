"""Phase 18: Telephony/SIP Base Integration."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_18_telephony_sip_base_integration.md"
    )
    assert plan.is_file()


def test_mulaw_transcoder_exists() -> None:
    try:
        from telephony_gateway.transcoding.mulaw import mulaw_to_pcm16  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 18 implementation pending: {exc}")
    out = mulaw_to_pcm16(b"\xff" * 160)
    assert len(out) == 320  # 8-bit mu-law -> 16-bit PCM
