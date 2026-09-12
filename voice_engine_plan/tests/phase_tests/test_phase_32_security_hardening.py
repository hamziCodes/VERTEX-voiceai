"""Phase 32: Security Hardening and Threat Controls."""

from __future__ import annotations

from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_32_security_hardening_and_threat_controls.md"
)
SECURITY_DOCS = REPO_ROOT / "docs" / "security"


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_security_docs_exist() -> None:
    for name in ("THREAT_MODEL.md", "ANTI_PATTERN_CHECKLIST.md", "PENTEST_READINESS.md"):
        path = SECURITY_DOCS / name
        assert path.is_file(), f"Missing doc {name}"


def test_threat_model_has_at_least_three_boundaries() -> None:
    threat_text = (SECURITY_DOCS / "THREAT_MODEL.md").read_text(encoding="utf-8")
    boundaries = [line for line in threat_text.splitlines() if line.strip().startswith("### Boundary")]
    assert len(boundaries) >= 3, f"Threat model must have >= 3 trust boundaries, found: {len(boundaries)}"


def test_anti_pattern_checklist_covers_file9() -> None:
    checklist = (SECURITY_DOCS / "ANTI_PATTERN_CHECKLIST.md").read_text(encoding="utf-8")
    for i in range(1, 21):
        assert f"| {i} |" in checklist, f"Checklist missing item #{i}"


def test_anti_patterns_test_file_has_at_least_10_tests() -> None:
    test_file = REPO_ROOT / "tests" / "security" / "test_anti_patterns.py"
    assert test_file.is_file()
    lines = test_file.read_text(encoding="utf-8").splitlines()
    test_funcs = [line for line in lines if line.strip().startswith("def test_")]
    assert len(test_funcs) >= 10, f"Expected >= 10 test functions, found {len(test_funcs)}"


def test_security_headers_middleware_registered() -> None:
    from control_plane.app import app
    from control_plane.middleware.security_headers import SecurityHeadersMiddleware

    middleware_types = [m.cls for m in app.user_middleware]
    assert SecurityHeadersMiddleware in middleware_types, "SecurityHeadersMiddleware not registered in app"


def test_ws_policy_enforces_max_frame_size() -> None:
    from worker_raw.security.ws_policy import WSSecurityPolicy, WSSecurityViolation

    policy = WSSecurityPolicy(max_frame_size=1024)
    assert policy.validate_frame_size(512) is True
    assert policy.validate_frame_size(b"\x00" * 1024) is True

    with pytest.raises(WSSecurityViolation):
        policy.validate_frame_size(1025)

    with pytest.raises(WSSecurityViolation):
        policy.validate_frame_size(b"\x00" * 2000)


def test_pentest_readiness_mentions_urdu_redaction_limitation() -> None:
    pentest_text = (SECURITY_DOCS / "PENTEST_READINESS.md").read_text(encoding="utf-8")
    assert "urdu" in pentest_text.lower()
    assert "redaction" in pentest_text.lower()

