"""Deterministic endpoint-delay candidates and offline comparison helpers."""

from __future__ import annotations

from dataclasses import dataclass

ENDPOINT_CANDIDATES_MS: tuple[int, ...] = (400, 550, 650, 960)


@dataclass(frozen=True)
class PauseFixture:
    """Annotated within-utterance pauses for one language fixture."""

    fixture_id: str
    language: str
    within_utterance_pauses_ms: tuple[int, ...]


@dataclass(frozen=True)
class EndpointBenchmarkResult:
    """Static latency/cutoff tradeoff for one endpoint candidate."""

    endpoint_ms: int
    fixture_count: int
    pause_count: int
    false_endpoint_count: int
    false_endpoint_rate: float
    added_latency_ms: int


def benchmark_endpoint_candidates(
    fixtures: tuple[PauseFixture, ...],
) -> tuple[EndpointBenchmarkResult, ...]:
    """Compare candidates against annotated pauses without provider traffic.

    A pause at least as long as the endpoint threshold would prematurely split
    the annotated utterance. Provider/network latency is deliberately excluded.
    """
    pauses = [
        pause
        for fixture in fixtures
        for pause in fixture.within_utterance_pauses_ms
    ]
    results: list[EndpointBenchmarkResult] = []
    for endpoint_ms in ENDPOINT_CANDIDATES_MS:
        false_endpoints = sum(pause >= endpoint_ms for pause in pauses)
        results.append(
            EndpointBenchmarkResult(
                endpoint_ms=endpoint_ms,
                fixture_count=len(fixtures),
                pause_count=len(pauses),
                false_endpoint_count=false_endpoints,
                false_endpoint_rate=(
                    false_endpoints / len(pauses) if pauses else 0.0
                ),
                added_latency_ms=endpoint_ms,
            )
        )
    return tuple(results)
