"""Durable Telnyx call identity, lifecycle, and command idempotency."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from core.db.async_pg import AsyncDatabase, get_default_database
from telephony_gateway.telnyx.models import TelnyxEventType, TelnyxWebhookEnvelope


class TelephonyAdmissionError(ValueError):
    """Fail-closed carrier admission or lifecycle identity error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TelephonyCallState(StrEnum):
    RECEIVED = "received"
    ADMITTED = "admitted"
    ANSWERED = "answered"
    MEDIA_ACTIVE = "media_active"
    ENDING = "ending"
    ENDED = "ended"
    FAILED = "failed"


_STATE_RANK = {
    TelephonyCallState.RECEIVED: 0,
    TelephonyCallState.ADMITTED: 1,
    TelephonyCallState.ANSWERED: 2,
    TelephonyCallState.MEDIA_ACTIVE: 3,
    TelephonyCallState.ENDING: 4,
    TelephonyCallState.ENDED: 5,
    TelephonyCallState.FAILED: 5,
}
_EVENT_STATE = {
    TelnyxEventType.CALL_INITIATED: TelephonyCallState.ADMITTED,
    TelnyxEventType.CALL_ANSWERED: TelephonyCallState.ANSWERED,
    TelnyxEventType.CALL_STREAMING_STARTED: TelephonyCallState.MEDIA_ACTIVE,
    TelnyxEventType.CALL_STREAMING_STOPPED: TelephonyCallState.ENDING,
    TelnyxEventType.CALL_HANGUP: TelephonyCallState.ENDED,
    TelnyxEventType.CALL_STREAMING_FAILED: TelephonyCallState.FAILED,
}


@dataclass(frozen=True, slots=True)
class DidBinding:
    did_id: UUID
    tenant_id: UUID
    agent_id: UUID
    did_number: str
    carrier: str
    active: bool
    published_version_id: UUID | None
    published_version: int | None


@dataclass(frozen=True, slots=True)
class TelephonyCall:
    call_id: UUID
    session_id: UUID
    tenant_id: UUID
    agent_id: UUID
    did_id: UUID
    did_number: str
    published_version_id: UUID
    published_version: int
    carrier: str
    call_control_id: str
    call_leg_id: str
    carrier_session_id: str
    direction: str
    state: TelephonyCallState
    state_changed_at: datetime
    disconnect_reason: str | None = None


@dataclass(frozen=True, slots=True)
class TelephonyCommand:
    command_id: UUID
    call_id: UUID
    tenant_id: UUID
    command_name: str
    idempotency_key: str
    status: str = "reserved"


def _owned_number(event: TelnyxWebhookEnvelope) -> str:
    payload = event.data.payload
    return str(payload.from_number if payload.direction == "outgoing" else payload.to)


def _target_state(event_type: TelnyxEventType) -> TelephonyCallState | None:
    return _EVENT_STATE.get(event_type)


def _disconnect_reason(event: TelnyxWebhookEnvelope) -> str | None:
    if event.data.event_type not in {
        TelnyxEventType.CALL_HANGUP,
        TelnyxEventType.CALL_STREAMING_FAILED,
    }:
        return None
    value = getattr(event.data.payload, "hangup_cause", None) or getattr(
        event.data.payload, "failure_reason", None
    )
    return str(value)[:255] if value else None


class InMemoryTelephonyRepository:
    """Deterministic lifecycle repository for offline tests only."""

    def __init__(self) -> None:
        self._dids: dict[tuple[str, str], DidBinding] = {}
        self._calls: dict[tuple[str, str], TelephonyCall] = {}
        self._events: set[UUID] = set()
        self._commands: dict[tuple[UUID, str], TelephonyCommand] = {}
        self._lock = asyncio.Lock()

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def command_count(self) -> int:
        return len(self._commands)

    def add_did(self, binding: DidBinding) -> None:
        self._dids[(binding.carrier, binding.did_number)] = binding

    async def resolve_did(
        self, did_number: str, *, carrier: str = "telnyx"
    ) -> DidBinding:
        binding = self._dids.get((carrier, did_number))
        if binding is None:
            raise TelephonyAdmissionError("did_not_found")
        if not binding.active:
            raise TelephonyAdmissionError("did_inactive")
        if binding.published_version_id is None or binding.published_version is None:
            raise TelephonyAdmissionError("agent_not_published")
        return binding

    async def get_call(
        self, carrier: str, call_control_id: str
    ) -> TelephonyCall | None:
        return self._calls.get((carrier, call_control_id))

    async def accept_once(self, event: TelnyxWebhookEnvelope) -> bool:
        async with self._lock:
            if event.data.id in self._events:
                return False
            payload = event.data.payload
            key = ("telnyx", payload.call_control_id)
            call = self._calls.get(key)
            owned_number = _owned_number(event)
            if call is None:
                binding = await self.resolve_did(owned_number)
                target = _target_state(event.data.event_type)
                state = target or TelephonyCallState.ADMITTED
                assert binding.published_version_id is not None
                assert binding.published_version is not None
                call = TelephonyCall(
                    call_id=uuid4(),
                    session_id=uuid4(),
                    tenant_id=binding.tenant_id,
                    agent_id=binding.agent_id,
                    did_id=binding.did_id,
                    did_number=binding.did_number,
                    published_version_id=binding.published_version_id,
                    published_version=binding.published_version,
                    carrier="telnyx",
                    call_control_id=payload.call_control_id,
                    call_leg_id=payload.call_leg_id,
                    carrier_session_id=payload.call_session_id,
                    direction=payload.direction or "incoming",
                    state=state,
                    state_changed_at=event.data.occurred_at,
                    disconnect_reason=_disconnect_reason(event),
                )
                self._calls[key] = call
            else:
                if (
                    call.did_number != owned_number
                    or call.call_leg_id != payload.call_leg_id
                    or call.carrier_session_id != payload.call_session_id
                ):
                    raise TelephonyAdmissionError("call_identity_mismatch")
                target = _target_state(event.data.event_type)
                if target is not None and _STATE_RANK[target] > _STATE_RANK[call.state]:
                    call = replace(
                        call,
                        state=target,
                        state_changed_at=event.data.occurred_at,
                        disconnect_reason=_disconnect_reason(event)
                        or call.disconnect_reason,
                    )
                    self._calls[key] = call
            self._events.add(event.data.id)
            return True

    async def reserve_command(
        self,
        *,
        call_id: UUID,
        tenant_id: UUID,
        command_name: str,
        idempotency_key: str,
    ) -> TelephonyCommand:
        if not command_name.strip() or not idempotency_key.strip():
            raise ValueError("command_name and idempotency_key are required")
        async with self._lock:
            key = (tenant_id, idempotency_key)
            existing = self._commands.get(key)
            if existing is not None:
                if existing.call_id != call_id or existing.command_name != command_name:
                    raise TelephonyAdmissionError("command_idempotency_conflict")
                return existing
            command = TelephonyCommand(
                command_id=uuid4(),
                call_id=call_id,
                tenant_id=tenant_id,
                command_name=command_name,
                idempotency_key=idempotency_key,
            )
            self._commands[key] = command
            return command


class PostgresTelephonyRepository:
    """Atomic PostgreSQL event sink and telephony lifecycle repository."""

    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    @staticmethod
    async def _resolve_on(connection: Any, did_number: str, carrier: str) -> DidBinding:
        cursor = await connection.execute(
            "SELECT d.id, d.tenant_id, d.agent_id, d.did_number, d.carrier, "
            "d.status, v.version_id, v.version FROM telephony_dids d "
            "JOIN tenants t ON t.id = d.tenant_id AND t.deleted_at IS NULL "
            "JOIN agents a ON a.id = d.agent_id AND a.tenant_id = d.tenant_id "
            "LEFT JOIN agent_configs ac ON ac.agent_id = d.agent_id "
            "AND ac.tenant_id = d.tenant_id "
            "LEFT JOIN agent_config_versions v ON v.agent_id = ac.agent_id "
            "AND v.tenant_id = ac.tenant_id AND v.version = ac.current_version "
            "WHERE d.did_number = %s AND d.carrier = %s FOR SHARE OF d",
            (did_number, carrier),
        )
        row = await cursor.fetchone()
        if row is None:
            raise TelephonyAdmissionError("did_not_found")
        binding = DidBinding(
            did_id=row[0],
            tenant_id=row[1],
            agent_id=row[2],
            did_number=row[3],
            carrier=row[4],
            active=row[5] == "active",
            published_version_id=row[6],
            published_version=row[7],
        )
        if not binding.active:
            raise TelephonyAdmissionError("did_inactive")
        if binding.published_version_id is None or binding.published_version is None:
            raise TelephonyAdmissionError("agent_not_published")
        return binding

    async def resolve_did(
        self, did_number: str, *, carrier: str = "telnyx"
    ) -> DidBinding:
        async with self.database.platform_transaction() as connection:
            return await self._resolve_on(connection, did_number, carrier)

    @staticmethod
    def _call_columns() -> str:
        return (
            "call_id, internal_session_id, tenant_id, agent_id, did_id, did_number, "
            "published_version_id, published_version, carrier, call_control_id, "
            "call_leg_id, carrier_session_id, direction, state, state_changed_at, "
            "disconnect_reason"
        )

    @staticmethod
    def _call_from_row(row: Any) -> TelephonyCall:
        return TelephonyCall(
            call_id=row[0],
            session_id=row[1],
            tenant_id=row[2],
            agent_id=row[3],
            did_id=row[4],
            did_number=row[5],
            published_version_id=row[6],
            published_version=row[7],
            carrier=row[8],
            call_control_id=row[9],
            call_leg_id=row[10],
            carrier_session_id=row[11],
            direction=row[12],
            state=TelephonyCallState(row[13]),
            state_changed_at=row[14],
            disconnect_reason=row[15],
        )

    async def get_call(
        self, carrier: str, call_control_id: str
    ) -> TelephonyCall | None:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT " + self._call_columns() + " FROM telephony_calls "
                "WHERE carrier = %s AND call_control_id = %s",
                (carrier, call_control_id),
            )
            row = await cursor.fetchone()
        return self._call_from_row(row) if row else None

    async def accept_once(self, event: TelnyxWebhookEnvelope) -> bool:
        payload = event.data.payload
        carrier = "telnyx"
        now = datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"event:{event.data.id}",),
            )
            existing = await connection.execute(
                "SELECT 1 FROM telephony_events WHERE carrier_event_id = %s::uuid",
                (str(event.data.id),),
            )
            if await existing.fetchone() is not None:
                return False
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"call:{carrier}:{payload.call_control_id}",),
            )
            selected = await connection.execute(
                "SELECT " + self._call_columns() + " FROM telephony_calls "
                "WHERE carrier = %s AND call_control_id = %s FOR UPDATE",
                (carrier, payload.call_control_id),
            )
            row = await selected.fetchone()
            owned_number = _owned_number(event)
            target = _target_state(event.data.event_type)
            applied = False
            if row is None:
                binding = await self._resolve_on(connection, owned_number, carrier)
                assert binding.published_version_id is not None
                assert binding.published_version is not None
                state = target or TelephonyCallState.ADMITTED
                inserted = await connection.execute(
                    "INSERT INTO telephony_calls ("
                    + self._call_columns()
                    + ", received_at, admitted_at, created_at, updated_at) VALUES ("
                    + ", ".join(["%s"] * 20)
                    + ") RETURNING "
                    + self._call_columns(),
                    (
                        uuid4(),
                        uuid4(),
                        binding.tenant_id,
                        binding.agent_id,
                        binding.did_id,
                        binding.did_number,
                        binding.published_version_id,
                        binding.published_version,
                        carrier,
                        payload.call_control_id,
                        payload.call_leg_id,
                        payload.call_session_id,
                        payload.direction or "incoming",
                        state.value,
                        event.data.occurred_at,
                        _disconnect_reason(event),
                        now,
                        now,
                        now,
                        now,
                    ),
                )
                call = self._call_from_row(await inserted.fetchone())
                applied = target is not None
            else:
                call = self._call_from_row(row)
                if (
                    call.did_number != owned_number
                    or call.call_leg_id != payload.call_leg_id
                    or call.carrier_session_id != payload.call_session_id
                ):
                    raise TelephonyAdmissionError("call_identity_mismatch")
                if target is not None and _STATE_RANK[target] > _STATE_RANK[call.state]:
                    updated = await connection.execute(
                        "UPDATE telephony_calls SET state = %s, state_changed_at = %s, "
                        "disconnect_reason = COALESCE(%s, disconnect_reason), "
                        "updated_at = %s "
                        "WHERE call_id = %s RETURNING " + self._call_columns(),
                        (
                            target.value,
                            event.data.occurred_at,
                            _disconnect_reason(event),
                            now,
                            call.call_id,
                        ),
                    )
                    call = self._call_from_row(await updated.fetchone())
                    applied = True
            await connection.execute(
                "INSERT INTO telephony_events (carrier_event_id, tenant_id, call_id, "
                "carrier, event_type, occurred_at, received_at, state_applied) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    event.data.id,
                    call.tenant_id,
                    call.call_id,
                    carrier,
                    event.data.event_type.value,
                    event.data.occurred_at,
                    now,
                    applied,
                ),
            )
        return True

    async def reserve_command(
        self, *, call_id: UUID, tenant_id: UUID, command_name: str, idempotency_key: str
    ) -> TelephonyCommand:
        if not command_name.strip() or not idempotency_key.strip():
            raise ValueError("command_name and idempotency_key are required")
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "INSERT INTO telephony_commands (command_id, tenant_id, call_id, "
                "command_name, idempotency_key) VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, idempotency_key) DO UPDATE SET "
                "idempotency_key = telephony_commands.idempotency_key RETURNING "
                "command_id, call_id, tenant_id, command_name, idempotency_key, status",
                (uuid4(), tenant_id, call_id, command_name, idempotency_key),
            )
            row = await cursor.fetchone()
        if row[1] != call_id or row[3] != command_name:
            raise TelephonyAdmissionError("command_idempotency_conflict")
        return TelephonyCommand(
            command_id=row[0],
            call_id=row[1],
            tenant_id=row[2],
            command_name=row[3],
            idempotency_key=row[4],
            status=row[5],
        )
