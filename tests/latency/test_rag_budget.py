from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from core.latency.waterfall import LatencyWaterfall
from core.rag.prompt_context import KnowledgeContextService, RetrievalBudget


@pytest.mark.asyncio
async def test_soft_budget_is_measured_without_discarding_results() -> None:
    class _SlowSuccess:
        async def retrieve(self, *_args, **_kwargs):
            await asyncio.sleep(0.02)
            return []

    service = KnowledgeContextService(
        _SlowSuccess(), budget=RetrievalBudget(soft_ms=5, hard_ms=100)
    )
    result = await service.retrieve(
        query="policy",
        tenant_id=uuid4(),
        agent_id=uuid4(),
        agent_config_version=1,
        plan_hash="plan",
        knowledge_base_ids=(str(uuid4()),),
    )
    assert result.status == "no_results"
    assert result.soft_budget_exceeded is True
    assert result.duration_ms >= 5


@pytest.mark.asyncio
async def test_hard_budget_cancels_and_returns_degraded_result() -> None:
    cancelled = asyncio.Event()

    class _TooSlow:
        async def retrieve(self, *_args, **_kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    service = KnowledgeContextService(
        _TooSlow(), budget=RetrievalBudget(soft_ms=5, hard_ms=20)
    )
    result = await service.retrieve(
        query="policy",
        tenant_id=uuid4(),
        agent_id=uuid4(),
        agent_config_version=1,
        plan_hash="plan",
        knowledge_base_ids=(str(uuid4()),),
    )
    assert result.status == "timeout"
    assert result.error_category == "hard_timeout"
    assert result.chunks == []
    await asyncio.wait_for(cancelled.wait(), timeout=0.2)


def test_latency_payload_exposes_rag_outcome_without_content() -> None:
    waterfall = LatencyWaterfall(
        session_id=uuid4(),
        stt_final_ms=100.0,
        rag_retrieve_ms=180.0,
        rag_status="timeout",
        rag_result_count=0,
        rag_cache_hit=False,
        rag_soft_budget_exceeded=True,
        rag_error_category="hard_timeout",
    )
    payload = waterfall.to_metric_payload()
    assert payload["durations_ms"]["rag"] == 80.0
    assert payload["rag"] == {
        "status": "timeout",
        "result_count": 0,
        "cache_hit": False,
        "soft_budget_exceeded": True,
        "error_category": "hard_timeout",
    }
    assert "content" not in payload["rag"]
