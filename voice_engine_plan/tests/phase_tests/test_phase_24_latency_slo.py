"""Phase 24: Latency Budget Enforcement & SLO Policies Test Suite."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from core.latency.collector import LatencyCollector
from core.latency.demotion import LatencyDemotionRule
from core.latency.playback import PlaybackMetricHandler
from core.latency.slo_policy import SLOPolicy
from core.latency.waterfall import LatencyWaterfall, StageBudget
from core.latency.benchmarks.harness import LatencyBenchmarkHarness

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_24_latency_budget_enforcement_and_slo_policies.md"
    )
    assert plan.is_file()


def test_waterfall_computes_correct_deltas() -> None:
    waterfall = LatencyWaterfall(
        session_id=uuid4(),
        vad_end_of_speech_ms=1000.0,
        playback_start_ms=1450.0,
    )
    e2e = waterfall.compute_e2e_latency()
    assert e2e == 450.0


def test_playback_metric_handler_attaches_timestamp() -> None:
    waterfall = LatencyWaterfall(
        session_id=uuid4(),
        vad_end_of_speech_ms=2000.0,
    )
    e2e = PlaybackMetricHandler.handle_playback_started(waterfall, 2400.0)
    assert waterfall.playback_start_ms == 2400.0
    assert e2e == 400.0


def test_single_turn_is_not_misreported_as_a_p50_breach() -> None:
    slo = SLOPolicy(e2e_p50_target_ms=400.0, alert_on_breach=True)
    collector = LatencyCollector(slo_policy=slo)

    waterfall = LatencyWaterfall(
        session_id=uuid4(),
        vad_end_of_speech_ms=1000.0,
        playback_start_ms=1600.0,  # 600 ms > 400 ms target
    )

    result = collector.record_turn(waterfall)
    assert result.total_e2e_ms == 600.0
    assert collector.warnings_emitted == []
    assert collector.percentile_summary()["p50_ms"] == 0.0


def test_demotion_does_not_trigger_when_enforce_demotion_false() -> None:
    slo = SLOPolicy(enforce_demotion=False)  # Global default false in v1
    rule = LatencyDemotionRule(slow_turns_threshold=3)

    for _ in range(5):
        triggered = rule.record_turn_latency("elevenlabs", latency_ms=500.0, budget_ms=150.0, slo_policy=slo)
        assert triggered is False  # Demotion skipped in warn-only mode


def test_demotion_triggers_when_opt_in_true_after_n_slow_turns() -> None:
    slo = SLOPolicy(enforce_demotion=True)  # Enterprise opt-in
    rule = LatencyDemotionRule(slow_turns_threshold=3)

    triggered1 = rule.record_turn_latency("elevenlabs", latency_ms=500.0, budget_ms=150.0, slo_policy=slo)
    assert triggered1 is False

    triggered2 = rule.record_turn_latency("elevenlabs", latency_ms=500.0, budget_ms=150.0, slo_policy=slo)
    assert triggered2 is False

    triggered3 = rule.record_turn_latency("elevenlabs", latency_ms=500.0, budget_ms=150.0, slo_policy=slo)
    assert triggered3 is True  # Demotion triggered on 3rd slow turn


def test_benchmark_harness_produces_p50_p95_report() -> None:
    harness = LatencyBenchmarkHarness()
    for lat in [300.0, 400.0, 450.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0, 1200.0]:
        harness.add_waterfall(
            LatencyWaterfall(
                session_id=uuid4(),
                vad_end_of_speech_ms=1000.0,
                playback_start_ms=1000.0 + lat,
            )
        )

    report = harness.generate_report()
    assert report.total_turns == 10
    assert report.p50_ms >= 600.0
    assert report.p95_ms >= 1000.0
