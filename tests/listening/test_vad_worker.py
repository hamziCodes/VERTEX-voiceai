"""Bounded shared VAD execution contracts."""

from __future__ import annotations

from core.listening.vad_worker import VADWorker
from worker_raw.orchestration.pipeline import PipelineOrchestrator


def test_vad_workers_share_one_bounded_executor() -> None:
    first = VADWorker()
    second = VADWorker()

    assert first._executor is second._executor
    assert first._executor._max_workers == 2

    first.shutdown()
    second.shutdown()


def test_pipeline_always_uses_bounded_vad_worker(monkeypatch) -> None:
    monkeypatch.delenv("UCVE_PIPELINE_V2", raising=False)

    orchestrator = PipelineOrchestrator()

    assert orchestrator._vad_worker is not None
    orchestrator._vad_worker.shutdown()
