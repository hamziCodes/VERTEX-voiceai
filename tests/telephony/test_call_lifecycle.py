from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from core.db.repos.telephony_repo import (
    DidBinding,
    InMemoryTelephonyRepository,
    TelephonyAdmissionError,
    TelephonyCallState,
)
from telephony_gateway.failover import TelephonyFailoverRouter, TrunkUnavailableError
from telephony_gateway.resolver.sip_participant_resolver import SIPParticipantResolver
from telephony_gateway.telnyx.models import TelnyxWebhookEnvelope

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
TENANT_ID = UUID("00000000-0000-4000-8000-000000000001")
AGENT_ID = UUID("00000000-0000-4000-8000-0000000000a1")
DID_ID = UUID("00000000-0000-4000-8000-0000000000d1")
DID = "+18005550199"


def _event(
    event_type: str,
    *,
    event_id: UUID | None = None,
    occurred_at: datetime = NOW,
    call_control_id: str = "v3:test-call-control",
    to_number: str = DID,
) -> TelnyxWebhookEnvelope:
    return TelnyxWebhookEnvelope.model_validate(
        {
            "data": {
                "id": str(event_id or uuid4()),
                "event_type": event_type,
                "occurred_at": occurred_at.isoformat(),
                "record_type": "event",
                "payload": {
                    "call_control_id": call_control_id,
                    "call_leg_id": "call-leg-1",
                    "call_session_id": "carrier-session-1",
                    "connection_id": "connection-1",
                    "from": "+14155550100",
                    "to": to_number,
                    "direction": "incoming",
                    "hangup_cause": "normal_clearing",
                },
            }
        }
    )


def _repo(
    *, active: bool = True, published: bool = True
) -> InMemoryTelephonyRepository:
    repository = InMemoryTelephonyRepository()
    repository.add_did(
        DidBinding(
            did_id=DID_ID,
            tenant_id=TENANT_ID,
            agent_id=AGENT_ID,
            did_number=DID,
            carrier="telnyx",
            active=active,
            published_version_id=uuid4() if published else None,
            published_version=3 if published else None,
        )
    )
    return repository


@pytest.mark.asyncio
async def test_one_carrier_call_has_one_session_and_duplicate_event_is_atomic() -> None:
    repository = _repo()
    initiated = _event("call.initiated")

    assert await repository.accept_once(initiated) is True
    first = await repository.get_call("telnyx", "v3:test-call-control")
    assert first is not None
    assert first.state is TelephonyCallState.ADMITTED
    assert first.tenant_id == TENANT_ID
    assert first.agent_id == AGENT_ID
    assert first.published_version == 3

    assert await repository.accept_once(initiated) is False
    answered = _event("call.answered", occurred_at=NOW + timedelta(seconds=1))
    assert await repository.accept_once(answered) is True
    second = await repository.get_call("telnyx", "v3:test-call-control")
    assert second is not None
    assert second.session_id == first.session_id
    assert second.state is TelephonyCallState.ANSWERED
    assert repository.event_count == 2


@pytest.mark.asyncio
async def test_reordered_events_are_kept_without_state_regression() -> None:
    repository = _repo()

    await repository.accept_once(_event("call.streaming.started"))
    call = await repository.get_call("telnyx", "v3:test-call-control")
    assert call is not None and call.state is TelephonyCallState.MEDIA_ACTIVE

    await repository.accept_once(
        _event("call.initiated", occurred_at=NOW - timedelta(seconds=2))
    )
    call = await repository.get_call("telnyx", "v3:test-call-control")
    assert call is not None and call.state is TelephonyCallState.MEDIA_ACTIVE

    await repository.accept_once(_event("call.hangup"))
    await repository.accept_once(_event("call.answered"))
    call = await repository.get_call("telnyx", "v3:test-call-control")
    assert call is not None and call.state is TelephonyCallState.ENDED
    assert call.disconnect_reason == "normal_clearing"
    assert repository.event_count == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repository", "number", "code"),
    [
        (InMemoryTelephonyRepository(), "+15551234567", "did_not_found"),
        (_repo(active=False), DID, "did_inactive"),
        (_repo(published=False), DID, "agent_not_published"),
    ],
)
async def test_unknown_inactive_and_unpublished_dids_fail_closed(
    repository: InMemoryTelephonyRepository, number: str, code: str
) -> None:
    with pytest.raises(TelephonyAdmissionError, match=code):
        await repository.accept_once(_event("call.initiated", to_number=number))
    assert repository.event_count == 0


@pytest.mark.asyncio
async def test_existing_call_rejects_did_ownership_change() -> None:
    repository = _repo()
    await repository.accept_once(_event("call.initiated"))

    with pytest.raises(TelephonyAdmissionError, match="call_identity_mismatch"):
        await repository.accept_once(_event("call.answered", to_number="+18005550200"))
    assert repository.event_count == 1


@pytest.mark.asyncio
async def test_command_reservation_is_idempotent_and_separate_from_event_receipt() -> (
    None
):
    repository = _repo()
    await repository.accept_once(_event("call.initiated"))
    call = await repository.get_call("telnyx", "v3:test-call-control")
    assert call is not None

    first = await repository.reserve_command(
        call_id=call.call_id,
        tenant_id=TENANT_ID,
        command_name="answer",
        idempotency_key="answer:v3:test-call-control",
    )
    second = await repository.reserve_command(
        call_id=call.call_id,
        tenant_id=TENANT_ID,
        command_name="answer",
        idempotency_key="answer:v3:test-call-control",
    )

    assert first.command_id == second.command_id
    assert repository.command_count == 1


@pytest.mark.asyncio
async def test_resolver_requires_explicit_repository_and_strict_e164() -> None:
    repository = _repo()
    resolver = SIPParticipantResolver(repository)

    binding = await resolver.resolve(DID)
    assert binding.tenant_id == TENANT_ID
    assert binding.agent_id == AGENT_ID
    with pytest.raises(ValueError, match="E.164"):
        await resolver.resolve("800-555-0199")
    with pytest.raises(TelephonyAdmissionError, match="did_not_found"):
        await resolver.resolve("+15551234567")


@pytest.mark.asyncio
async def test_missing_durable_trunk_has_no_fabricated_default() -> None:
    class Connection:
        async def execute(self, *_args):
            return None

        async def fetch(self, *_args):
            return []

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *_args):
            return None

    class Pool:
        def acquire(self):
            return Acquire()

    with pytest.raises(TrunkUnavailableError, match="No enabled telephony trunk"):
        await TelephonyFailoverRouter.from_db(Pool(), TENANT_ID)
