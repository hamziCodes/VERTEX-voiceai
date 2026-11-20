from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from core.db.repos.post_call_repo import InMemoryPostCallRepository
from post_call.jobs.models import PostCallIntelligenceResult
from post_call.jobs.repository import InMemoryPostCallJobRepository
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.policy import PostCallPolicy
from post_call.models.recording import CallRecording, RecordingState
from post_call.review.models import ReviewRequest
from tests.studio.test_identity_api import _create_workspace, _headers


async def _seed_calls(repository: InMemoryPostCallRepository, tenant_id: UUID):
    now = datetime.now(UTC)
    records = []
    for offset in range(3):
        session_id = uuid4()
        record = await repository.start_call(
            tenant_id=tenant_id,
            agent_id=uuid4(),
            session_id=session_id,
            started_at=now - timedelta(minutes=offset),
            transport_type="websocket",
            policy=PostCallPolicy(),
            provider_snapshot={"stt": "gladia"},
        )
        await repository.append_turn(
            tenant_id=tenant_id,
            session_id=session_id,
            ordinal=0,
            turn=DiarizedTurn(
                speaker="user", text=f"turn {offset}", start_ms=0, end_ms=100
            ),
        )
        records.append(record)
    return records


def test_conversation_list_is_cursor_paginated_and_tenant_scoped(studio_api) -> None:
    client, app = studio_api
    tenant_id, _ = _create_workspace(client)
    calls = InMemoryPostCallRepository()
    asyncio.run(_seed_calls(calls, tenant_id))
    app.state.post_call_repository = calls
    app.state.post_call_job_repository = InMemoryPostCallJobRepository(calls)

    first = client.get(
        "/v1/conversations?limit=2", headers=_headers("owner-token", tenant_id)
    )
    second = client.get(
        f"/v1/conversations?limit=2&cursor={first.json()['next_cursor']}",
        headers=_headers("owner-token", tenant_id),
    )
    wrong_tenant = client.get(
        "/v1/conversations", headers=_headers("owner-token", UUID(int=1))
    )

    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    assert len(second.json()["items"]) == 1
    first_ids = {item["call_id"] for item in first.json()["items"]}
    second_ids = {item["call_id"] for item in second.json()["items"]}
    assert not (first_ids & second_ids)
    assert wrong_tenant.status_code == 403


def test_conversation_detail_hides_storage_reference_and_reports_intelligence(
    studio_api,
) -> None:
    client, app = studio_api
    tenant_id, _ = _create_workspace(client)
    calls = InMemoryPostCallRepository()
    record = asyncio.run(_seed_calls(calls, tenant_id))[0]
    stored = calls._calls[(tenant_id, record.session_id)]
    stored.recording_state = RecordingState.AVAILABLE
    stored.recording = CallRecording(
        recording_s3_uri="post-call+s3://private/secret.wav",
        checksum="a" * 64,
        duration_sec=2.0,
        storage_region="pk-isb",
    )
    jobs = InMemoryPostCallJobRepository(calls)
    app.state.post_call_repository = calls
    app.state.post_call_job_repository = jobs

    unavailable = client.get(
        f"/v1/conversations/{record.call_id}/intelligence",
        headers=_headers("owner-token", tenant_id),
    )
    result = PostCallIntelligenceResult(
        tenant_id=tenant_id,
        call_id=record.call_id,
        summary={"text": "resolved"},
        provider_snapshot={"provider": "offline-test"},
    )
    calls._post_call_results[(tenant_id, record.call_id)] = result
    calls._post_call_reviews[uuid4()] = ReviewRequest(
        tenant_id=tenant_id,
        call_id=record.call_id,
        result_id=result.result_id,
        reasons=("sensitive_field",),
    )
    detail = client.get(
        f"/v1/conversations/{record.call_id}",
        headers=_headers("owner-token", tenant_id),
    )
    intelligence = client.get(
        f"/v1/conversations/{record.call_id}/intelligence",
        headers=_headers("owner-token", tenant_id),
    )

    assert unavailable.status_code == 200
    assert unavailable.json() == {
        "state": "unavailable",
        "result": None,
        "review": None,
    }
    assert detail.status_code == 200
    assert detail.json()["recording"] == {
        "state": "available",
        "duration_sec": 2.0,
        "access": "gated",
    }
    assert "secret.wav" not in detail.text
    assert intelligence.json()["state"] == "available"
    assert intelligence.json()["review"]["state"] == "pending"
