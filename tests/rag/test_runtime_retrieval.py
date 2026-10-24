from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from core.providers.interfaces.llm import LLMStreamChunk
from core.rag.models import KnowledgeBaseChunk
from core.rag.prompt_context import KnowledgeContextService, RetrievalBudget
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


class _ScopedRetriever:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 3, **scope):
        self.calls.append(
            {"query": query, "tenant_id": tenant_id, "top_k": top_k, **scope}
        )
        return [
            KnowledgeBaseChunk(
                tenant_id=tenant_id,
                knowledge_base_id=scope["knowledge_base_id"],
                source_document_id=uuid4(),
                revision=7,
                text="Fourteen day refund policy.",
                citation={"page": 2},
                score=0.93,
            )
        ]


@pytest.mark.asyncio
async def test_runtime_retrieval_uses_published_scope_and_cache() -> None:
    retriever = _ScopedRetriever()
    service = KnowledgeContextService(retriever)
    tenant_id, agent_id, base_id = uuid4(), uuid4(), uuid4()

    first = await service.retrieve(
        query=" Refund policy ",
        tenant_id=tenant_id,
        agent_id=agent_id,
        agent_config_version=4,
        plan_hash="plan-a",
        knowledge_base_ids=(str(base_id),),
    )
    second = await service.retrieve(
        query="refund   policy",
        tenant_id=tenant_id,
        agent_id=agent_id,
        agent_config_version=4,
        plan_hash="plan-a",
        knowledge_base_ids=(str(base_id),),
    )

    assert first.status == "ok"
    assert second.cache_hit is True
    assert len(retriever.calls) == 1
    assert retriever.calls[0]["agent_id"] == agent_id
    assert retriever.calls[0]["agent_config_version"] == 4
    assert retriever.calls[0]["knowledge_base_id"] == base_id

    await service.retrieve(
        query="refund policy",
        tenant_id=tenant_id,
        agent_id=agent_id,
        agent_config_version=5,
        plan_hash="plan-b",
        knowledge_base_ids=(str(base_id),),
    )
    assert len(retriever.calls) == 2


@pytest.mark.asyncio
async def test_invalid_published_base_id_degrades_without_retrieval() -> None:
    retriever = _ScopedRetriever()
    result = await KnowledgeContextService(retriever).retrieve(
        query="policy",
        tenant_id=uuid4(),
        agent_id=uuid4(),
        agent_config_version=1,
        plan_hash="plan",
        knowledge_base_ids=("not-a-uuid",),
    )
    assert result.status == "invalid_scope"
    assert result.chunks == []
    assert retriever.calls == []


@pytest.mark.asyncio
async def test_retrieval_error_is_explicit_and_non_blocking() -> None:
    class _Broken:
        async def retrieve(self, *_args, **_kwargs):
            raise RuntimeError("database DSN must never leak")

    result = await KnowledgeContextService(_Broken()).retrieve(
        query="policy",
        tenant_id=uuid4(),
        agent_id=uuid4(),
        agent_config_version=1,
        plan_hash="plan",
        knowledge_base_ids=(str(uuid4()),),
    )
    assert result.status == "error"
    assert result.error_category == "retrieval_error"
    assert result.chunks == []


@pytest.mark.asyncio
async def test_no_result_is_truthful() -> None:
    class _Empty:
        async def retrieve(self, *_args, **_kwargs):
            return []

    result = await KnowledgeContextService(_Empty()).retrieve(
        query="policy",
        tenant_id=uuid4(),
        agent_id=uuid4(),
        agent_config_version=1,
        plan_hash="plan",
        knowledge_base_ids=(str(uuid4()),),
    )
    assert result.status == "no_results"
    assert result.chunks == []


@pytest.mark.asyncio
async def test_outer_cancellation_cancels_retrieval_children() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class _Blocking:
        async def retrieve(self, *_args, **_kwargs):
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    service = KnowledgeContextService(_Blocking())
    task = asyncio.create_task(
        service.retrieve(
            query="policy",
            tenant_id=uuid4(),
            agent_id=uuid4(),
            agent_config_version=1,
            plan_hash="plan",
            knowledge_base_ids=(str(uuid4()),),
        )
    )
    await asyncio.wait_for(started.wait(), timeout=0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(cancelled.wait(), timeout=0.2)


def test_retrieval_budget_has_bounded_production_limits() -> None:
    budget = RetrievalBudget()
    assert budget.soft_ms == 250
    assert budget.hard_ms == 600
    assert budget.default_top_k == 4
    assert budget.max_top_k == 8


@pytest.mark.asyncio
async def test_pipeline_injects_scoped_knowledge_as_separate_data_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    retriever = _ScopedRetriever()
    captured: list[dict[str, object]] = []

    class _CaptureLLM:
        def health_check(self) -> bool:
            return True

        async def generate_stream(self, messages, config, cancellation_token=None):
            del config, cancellation_token
            captured.extend(messages)
            yield LLMStreamChunk(text="Refunds are available.", is_first_token=True)

    tenant_id, agent_id, base_id = uuid4(), uuid4(), uuid4()
    orchestrator = PipelineOrchestrator(rag_retriever=retriever)  # type: ignore[arg-type]
    orchestrator.llm_provider = _CaptureLLM()  # type: ignore[assignment]
    config = PipelineSessionConfig(
        session_id=str(uuid4()),
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        agent_config_version=4,
        session_plan_hash="published-plan-hash",
        knowledge_base_ids=(str(base_id),),
        system_prompt="Answer clinic questions.",
    )

    reply = await orchestrator.run_turn(config, "What is the refund policy?")
    await orchestrator.finalize_session(config)

    assert reply == "Refunds are available."
    assert captured[0]["role"] == "system"
    assert "Fourteen day refund policy." not in str(captured[0]["content"])
    assert captured[1]["role"] == "user"
    assert "UNTRUSTED_KNOWLEDGE_DATA" in str(captured[1]["content"])
    assert retriever.calls[0]["agent_config_version"] == 4
    assert retriever.calls[0]["knowledge_base_id"] == base_id


@pytest.mark.asyncio
async def test_pipeline_continues_without_knowledge_when_retrieval_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    captured: list[dict[str, object]] = []

    class _Broken:
        async def retrieve(self, *_args, **_kwargs):
            raise RuntimeError("sensitive database detail")

    class _CaptureLLM:
        def health_check(self) -> bool:
            return True

        async def generate_stream(self, messages, config, cancellation_token=None):
            del config, cancellation_token
            captured.extend(messages)
            yield LLMStreamChunk(text="I can still help.", is_first_token=True)

    tenant_id, agent_id, base_id = uuid4(), uuid4(), uuid4()
    orchestrator = PipelineOrchestrator(rag_retriever=_Broken())  # type: ignore[arg-type]
    orchestrator.llm_provider = _CaptureLLM()  # type: ignore[assignment]
    config = PipelineSessionConfig(
        session_id=str(uuid4()),
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        agent_config_version=1,
        session_plan_hash="published-plan-hash",
        knowledge_base_ids=(str(base_id),),
    )

    reply = await orchestrator.run_turn(config, "Can you help?")
    waterfall = orchestrator.latency_collector.collected_waterfalls[-1]
    await orchestrator.finalize_session(config)

    assert reply == "I can still help."
    assert [message["role"] for message in captured] == ["system", "user"]
    assert waterfall.rag_status == "error"
    assert waterfall.rag_error_category == "retrieval_error"
