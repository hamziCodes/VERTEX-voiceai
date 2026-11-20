from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from core.db.repos.post_call_repo import InMemoryPostCallRepository
from post_call.extraction.service import ExtractionService
from post_call.jobs.models import PostCallJobState
from post_call.jobs.repository import InMemoryPostCallJobRepository
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.disposition import CallDisposition
from post_call.models.policy import PostCallPolicy
from post_call.models.recording import RecordingState
from post_call.summarization.service import SummarizationService
from post_call.worker import PostCallJobWorker


class _ExtractionProvider:
    provider_id = "fixture"
    model_id = "extract-v1"

    async def extract_json(self, **_: object) -> object:
        return {
            "fields": {
                "patient_name": {
                    "value": "Ayesha",
                    "confidence": 0.99,
                    "evidence": [{"turn_id": 0, "quote": "name is Ayesha"}],
                }
            }
        }


class _SummaryProvider:
    provider_id = "fixture"
    model_id = "summary-v1"

    async def summarize_json(self, **_: object) -> object:
        return {
            "executive_summary": "Ayesha requested help.",
            "key_takeaways": ["Help requested"],
            "sentiment_trajectory": ["neutral"],
            "evidence": [{"turn_id": 0, "quote": "requested help"}],
        }


@pytest.mark.asyncio
async def test_worker_persists_result_and_review_once_after_restart() -> None:
    calls = InMemoryPostCallRepository()
    jobs = InMemoryPostCallJobRepository(calls)
    tenant_id, session_id = uuid4(), uuid4()
    started_at = datetime.now(UTC) - timedelta(seconds=2)
    await calls.start_call(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        session_id=session_id,
        started_at=started_at,
        transport_type="websocket",
        policy=PostCallPolicy(),
        provider_snapshot={},
        intelligence_config_snapshot={
            "extraction_schema": {
                "fields": [
                    {"name": "patient_name", "sensitive": True, "required": True}
                ]
            }
        },
    )
    await calls.append_turn(
        tenant_id=tenant_id,
        session_id=session_id,
        ordinal=0,
        turn=DiarizedTurn(
            speaker="user",
            text="My name is Ayesha and I requested help.",
            start_ms=0,
            end_ms=700,
        ),
    )
    call = await calls.finalize_call(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=started_at + timedelta(seconds=1),
        end_reason="complete",
        disposition=CallDisposition.COMPLETED,
        metrics_snapshot={},
        usage_snapshot={},
        recording_state=RecordingState.NOT_REQUESTED,
    )
    worker = PostCallJobWorker(
        call_repository=calls,
        job_repository=jobs,
        extraction_service=ExtractionService(provider=_ExtractionProvider()),
        summarization_service=SummarizationService(provider=_SummaryProvider()),
        worker_id="worker-a",
    )

    assert await worker.run_once() is True
    result = await jobs.get_result(tenant_id, call.call_id)

    assert result is not None
    review = await jobs.get_review_for_result(tenant_id, result.result_id)
    assert review is not None
    assert review.reasons == ("sensitive_field:patient_name",)
    assert await worker.run_once() is False
    only_job = next(iter(calls._post_call_jobs.values()))
    assert only_job.state is PostCallJobState.SUCCEEDED


class _InvalidExtractionProvider(_ExtractionProvider):
    async def extract_json(self, **_: object) -> object:
        return "invalid-json"


@pytest.mark.asyncio
async def test_invalid_provider_output_is_retryable_and_stores_no_result() -> None:
    calls = InMemoryPostCallRepository()
    jobs = InMemoryPostCallJobRepository(calls)
    tenant_id, session_id = uuid4(), uuid4()
    started_at = datetime.now(UTC) - timedelta(seconds=2)
    await calls.start_call(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        session_id=session_id,
        started_at=started_at,
        transport_type="websocket",
        policy=PostCallPolicy(),
        provider_snapshot={},
        intelligence_config_snapshot={
            "extraction_schema": {"fields": [{"name": "patient_name"}]}
        },
    )
    call = await calls.finalize_call(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=started_at + timedelta(seconds=1),
        end_reason="complete",
        disposition=CallDisposition.COMPLETED,
        metrics_snapshot={},
        usage_snapshot={},
        recording_state=RecordingState.NOT_REQUESTED,
    )
    worker = PostCallJobWorker(
        call_repository=calls,
        job_repository=jobs,
        extraction_service=ExtractionService(provider=_InvalidExtractionProvider()),
        summarization_service=SummarizationService(provider=_SummaryProvider()),
        worker_id="worker-a",
    )

    assert await worker.run_once() is True
    assert await jobs.get_result(tenant_id, call.call_id) is None
    only_job = next(iter(calls._post_call_jobs.values()))
    assert only_job.state is PostCallJobState.RETRY_WAIT
    assert only_job.last_error_code == "provider_output_invalid"


@pytest.mark.asyncio
async def test_external_action_without_schema_requires_review() -> None:
    calls = InMemoryPostCallRepository()
    jobs = InMemoryPostCallJobRepository(calls)
    tenant_id, session_id = uuid4(), uuid4()
    started_at = datetime.now(UTC) - timedelta(seconds=2)
    await calls.start_call(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        session_id=session_id,
        started_at=started_at,
        transport_type="websocket",
        policy=PostCallPolicy(requires_review_for_external_actions=False),
        provider_snapshot={},
        intelligence_config_snapshot={"external_action_configured": True},
    )
    call = await calls.finalize_call(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=started_at + timedelta(seconds=1),
        end_reason="complete",
        disposition=CallDisposition.COMPLETED,
        metrics_snapshot={},
        usage_snapshot={},
        recording_state=RecordingState.NOT_REQUESTED,
    )
    worker = PostCallJobWorker(
        call_repository=calls,
        job_repository=jobs,
        extraction_service=ExtractionService(provider=_ExtractionProvider()),
        summarization_service=SummarizationService(provider=_SummaryProvider()),
        worker_id="worker-a",
    )

    assert await worker.run_once() is True
    result = await jobs.get_result(tenant_id, call.call_id)
    assert result is not None
    review = await jobs.get_review_for_result(tenant_id, result.result_id)
    assert review is not None
    assert review.reasons == ("external_action_policy",)


@pytest.mark.asyncio
async def test_hipaa_without_baa_is_terminal_compliance_block() -> None:
    calls = InMemoryPostCallRepository()
    jobs = InMemoryPostCallJobRepository(calls)
    tenant_id, session_id = uuid4(), uuid4()
    started_at = datetime.now(UTC) - timedelta(seconds=2)
    await calls.start_call(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        session_id=session_id,
        started_at=started_at,
        transport_type="websocket",
        policy=PostCallPolicy(),
        provider_snapshot={},
        compliance_tier="hipaa",
        intelligence_config_snapshot={
            "extraction_schema": {"fields": [{"name": "patient_name"}]}
        },
    )
    call = await calls.finalize_call(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=started_at + timedelta(seconds=1),
        end_reason="complete",
        disposition=CallDisposition.COMPLETED,
        metrics_snapshot={},
        usage_snapshot={},
        recording_state=RecordingState.NOT_REQUESTED,
    )
    worker = PostCallJobWorker(
        call_repository=calls,
        job_repository=jobs,
        extraction_service=ExtractionService(
            provider=_ExtractionProvider(), hipaa_baa_acknowledged=False
        ),
        summarization_service=SummarizationService(provider=_SummaryProvider()),
        worker_id="worker-a",
    )

    assert await worker.run_once() is True
    assert await jobs.get_result(tenant_id, call.call_id) is None
    only_job = next(iter(calls._post_call_jobs.values()))
    assert only_job.state is PostCallJobState.DEAD_LETTER
    assert only_job.last_error_code == "compliance_blocked"
