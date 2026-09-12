"""Phase 31: Scaling and Runtime Resource Profiles."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_31_scaling_and_runtime_resource_profiles.md"
)
PROFILES = REPO_ROOT / "infra" / "scaling" / "profiles"


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_runtime_profiles_documented() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "standard" in text
    assert "active session" in text.lower()
    assert "None — fully deterministic" in text


def test_profile_yaml_files_exist() -> None:
    for name in ("dev.yaml", "standard.yaml", "high_density.yaml"):
        path = PROFILES / name
        assert path.is_file(), f"Missing profile {name}"


def test_profile_loader_loads_all_profiles() -> None:
    from core.runtime.profile_loader import load_profile

    dev = load_profile("dev")
    standard = load_profile("standard")
    high_density = load_profile("high_density")

    assert dev.max_sessions_per_worker == 5
    assert dev.silero_pool_size == 2

    assert standard.max_sessions_per_worker == 25
    assert standard.silero_pool_size == 4

    assert high_density.max_sessions_per_worker == 40
    assert high_density.silero_pool_size == 6

    # Verify dev profile has lower cap than standard
    assert dev.max_sessions_per_worker < standard.max_sessions_per_worker < high_density.max_sessions_per_worker


@pytest.mark.asyncio
async def test_session_admission_controller_enforces_cap() -> None:
    from core.runtime.admission import CapacityExceededError, SessionAdmissionController
    from core.runtime.profile_loader import load_profile

    dev_profile = load_profile("dev")
    controller = SessionAdmissionController(profile=dev_profile)

    assert controller.can_admit() is True
    assert controller.active_session_count == 0

    # Admit up to 5 sessions (dev profile max is 5)
    for i in range(5):
        admitted = await controller.acquire(f"session-{i}")
        assert admitted is True

    assert controller.active_session_count == 5
    assert controller.can_admit() is False

    # 6th session should be rejected with CapacityExceededError
    with pytest.raises(CapacityExceededError):
        await controller.acquire("session-overflow")

    # Release one session and verify admission works again
    await controller.release("session-0")
    assert controller.active_session_count == 4
    assert controller.can_admit() is True

    # Now we can acquire again
    admitted = await controller.acquire("session-new")
    assert admitted is True
    assert controller.active_session_count == 5


def test_resource_table_documents_memory_model() -> None:
    doc = (REPO_ROOT / "docs" / "scaling" / "RESOURCE_TABLE.md").read_text(encoding="utf-8")
    assert "150 MB" in doc or "150mb" in doc.lower()
    assert "50 MB" in doc or "50mb" in doc.lower()
    assert "3 MB" in doc or "3mb" in doc.lower()
    assert "Silero" in doc


def test_autoscaling_doc_references_active_sessions_metric() -> None:
    doc = (REPO_ROOT / "docs" / "scaling" / "AUTOSCALING.md").read_text(encoding="utf-8")
    assert "ucve_active_sessions" in doc
    assert "NOT supported" in doc or "not supported" in doc.lower()


def test_livekit_scale_lesson_doc_exists() -> None:
    doc = (REPO_ROOT / "docs" / "scaling" / "LIVEKIT_SCALE_LESSON.md").read_text(encoding="utf-8")
    assert "habiba" in doc.lower()
    assert "sovereign" in doc.lower()

