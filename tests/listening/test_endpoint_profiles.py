"""Offline endpoint-candidate comparison contracts."""

from __future__ import annotations

from core.listening.endpoint_profiles import (
    ENDPOINT_CANDIDATES_MS,
    PauseFixture,
    benchmark_endpoint_candidates,
)


def test_expected_endpoint_candidates_are_present() -> None:
    assert ENDPOINT_CANDIDATES_MS == (400, 550, 650, 960)


def test_benchmark_reports_latency_and_false_endpoint_tradeoff() -> None:
    fixtures = (
        PauseFixture("short-en", "en", (180, 420)),
        PauseFixture("short-ur", "ur", (240, 610)),
        PauseFixture("mixed-ur-en", "ur-en", (300, 720)),
    )

    results = benchmark_endpoint_candidates(fixtures)

    assert [result.endpoint_ms for result in results] == [400, 550, 650, 960]
    assert results[0].false_endpoint_count > results[-1].false_endpoint_count
    assert results[0].added_latency_ms < results[-1].added_latency_ms
    assert all(result.fixture_count == 3 for result in results)
