"""Durable tenant-isolated outbound call admission and idempotency."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from core.db.async_pg import AsyncDatabase, get_default_database
from telephony_gateway.outbound import (
    CallingWindow,
    InMemoryOutboundCallRepository,
    OutboundCallError,
    OutboundCallPolicy,
    OutboundCallRecord,
    OutboundCallRequest,
    OutboundCallSetup,
    OutboundCallStatus,
    _fingerprint,
)


def _request_fingerprint(request: OutboundCallRequest) -> str:
    encoded = json.dumps(
        [str(value) for value in _fingerprint(request)],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PostgresOutboundCallRepository:
    """Atomically enforce policy and persist one outbound call request."""

    def __init__(
        self,
        *,
        media_stream_url: str,
        database: AsyncDatabase | Any | None = None,
    ) -> None:
        if not media_stream_url.startswith("wss://"):
            raise ValueError("outbound media stream URL must use wss")
        self.database = database or get_default_database()
        self.media_stream_url = media_stream_url

    async def get_policy(self, tenant_id: UUID) -> OutboundCallPolicy:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT allowed_destinations, calling_timezone, window_start, "
                "window_end, max_concurrent_calls, max_calls_per_minute, "
                "daily_spend_cap_cents, reserved_spend_cents_per_call, "
                "max_call_duration_seconds FROM telephony_outbound_policies "
                "WHERE tenant_id = %s::uuid AND enabled = TRUE",
                (str(tenant_id),),
            )
            row = await cursor.fetchone()
        if row is None:
            raise OutboundCallError("outbound_policy_unavailable")
        try:
            return OutboundCallPolicy(
                allowed_destinations=frozenset(row[0]),
                calling_window=CallingWindow(
                    timezone=row[1], start=row[2], end=row[3]
                ),
                max_concurrent_calls=row[4],
                max_calls_per_minute=row[5],
                daily_spend_cap_cents=row[6],
                reserved_spend_cents_per_call=row[7],
                max_call_duration_seconds=row[8],
            )
        except (TypeError, ValueError) as exc:
            raise OutboundCallError("outbound_policy_invalid") from exc

    @staticmethod
    def _record_columns() -> str:
        return (
            "request_id, command_id, tenant_id, agent_id, destination, purpose, "
            "consent_reference, idempotency_key, status, requested_at, "
            "reserved_spend_cents, call_control_id, call_leg_id, call_session_id, "
            "failure_code, published_version_id, published_version, did_id, "
            "from_number, trunk_id, provider, credential_ref, connection_id, "
            "media_stream_url"
        )

    @staticmethod
    def _from_row(row: Any) -> OutboundCallRecord:
        request = OutboundCallRequest(
            tenant_id=row[2],
            agent_id=row[3],
            destination=row[4],
            purpose=row[5],
            consent_reference=row[6],
            idempotency_key=row[7],
        )
        setup = OutboundCallSetup(
            tenant_id=row[2],
            agent_id=row[3],
            published_version_id=row[15],
            published_version=row[16],
            did_id=row[17],
            from_number=row[18],
            trunk_id=row[19],
            provider=row[20],
            credential_ref=row[21],
            connection_id=row[22],
            media_stream_url=row[23],
        )
        return OutboundCallRecord(
            request_id=row[0],
            command_id=row[1],
            request=request,
            setup=setup,
            status=OutboundCallStatus(row[8]),
            requested_at=row[9],
            reserved_spend_cents=row[10],
            call_control_id=row[11],
            call_leg_id=row[12],
            call_session_id=row[13],
            failure_code=row[14],
        )

    async def reserve(
        self,
        request: OutboundCallRequest,
        policy: OutboundCallPolicy,
        now: datetime,
    ) -> tuple[OutboundCallRecord, bool]:
        InMemoryOutboundCallRepository._validate_request(request)
        if now.tzinfo is None:
            raise ValueError("outbound reservation requires an aware timestamp")
        fingerprint = _request_fingerprint(request)
        async with self.database.tenant_transaction(
            str(request.tenant_id)
        ) as connection:
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"outbound:{request.tenant_id}",),
            )
            existing_cursor = await connection.execute(
                "SELECT " + self._record_columns() + ", request_fingerprint "
                "FROM telephony_outbound_requests WHERE tenant_id = %s::uuid "
                "AND idempotency_key = %s",
                (str(request.tenant_id), request.idempotency_key),
            )
            existing = await existing_cursor.fetchone()
            if existing is not None:
                if existing[24] != fingerprint:
                    raise OutboundCallError("idempotency_conflict")
                return self._from_row(existing), False

            if request.destination not in policy.allowed_destinations:
                raise OutboundCallError("destination_not_allowed")
            if not policy.calling_window.allows(now):
                raise OutboundCallError("outside_calling_window")

            setup_cursor = await connection.execute(
                "SELECT v.version_id, v.version, d.id, d.did_number, s.id, "
                "s.provider, s.credentials_ref, s.connection_id "
                "FROM agent_configs ac JOIN agent_config_versions v ON "
                "v.tenant_id = ac.tenant_id AND v.agent_id = ac.agent_id "
                "AND v.version = ac.current_version JOIN telephony_dids d ON "
                "d.tenant_id = ac.tenant_id AND d.agent_id = ac.agent_id "
                "AND d.status = 'active' AND d.carrier = 'telnyx' "
                "JOIN sip_trunks s ON s.tenant_id = ac.tenant_id "
                "AND s.provider = 'telnyx' AND s.enabled = TRUE "
                "WHERE ac.tenant_id = %s::uuid AND ac.agent_id = %s::uuid "
                "ORDER BY s.priority, d.created_at LIMIT 1 FOR SHARE OF ac, v, d, s",
                (str(request.tenant_id), str(request.agent_id)),
            )
            setup_row = await setup_cursor.fetchone()
            if setup_row is None:
                raise OutboundCallError("outbound_setup_unavailable")
            if not setup_row[6] or not setup_row[7]:
                raise OutboundCallError("outbound_setup_not_ready")

            active_cursor = await connection.execute(
                "SELECT COUNT(*) FROM telephony_outbound_requests WHERE "
                "tenant_id = %s::uuid AND status IN "
                "('reserved', 'submitting', 'submitted', 'ambiguous')",
                (str(request.tenant_id),),
            )
            if (await active_cursor.fetchone())[0] >= policy.max_concurrent_calls:
                raise OutboundCallError("concurrency_limit")
            recent_cursor = await connection.execute(
                "SELECT COUNT(*) FROM telephony_outbound_requests WHERE "
                "tenant_id = %s::uuid AND requested_at > %s",
                (str(request.tenant_id), now - timedelta(minutes=1)),
            )
            if (await recent_cursor.fetchone())[0] >= policy.max_calls_per_minute:
                raise OutboundCallError("rate_limit")
            day_start = now.astimezone(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            spend_cursor = await connection.execute(
                "SELECT COALESCE(SUM(reserved_spend_cents), 0) FROM "
                "telephony_outbound_requests WHERE tenant_id = %s::uuid "
                "AND requested_at >= %s",
                (str(request.tenant_id), day_start),
            )
            spent = (await spend_cursor.fetchone())[0]
            if (
                spent + policy.reserved_spend_cents_per_call
                > policy.daily_spend_cap_cents
            ):
                raise OutboundCallError("spend_limit")

            request_id, command_id = uuid4(), uuid4()
            inserted = await connection.execute(
                "INSERT INTO telephony_outbound_requests (request_id, command_id, "
                "tenant_id, agent_id, destination, purpose, consent_reference, "
                "idempotency_key, request_fingerprint, status, requested_at, "
                "reserved_spend_cents, published_version_id, published_version, "
                "did_id, from_number, trunk_id, provider, credential_ref, "
                "connection_id, media_stream_url) VALUES ("
                "%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, "
                "'reserved', %s, %s, %s::uuid, %s, %s::uuid, %s, %s::uuid, %s, "
                "%s, %s, %s) RETURNING " + self._record_columns(),
                (
                    str(request_id),
                    str(command_id),
                    str(request.tenant_id),
                    str(request.agent_id),
                    request.destination,
                    request.purpose.strip(),
                    request.consent_reference.strip(),
                    request.idempotency_key,
                    fingerprint,
                    now.astimezone(UTC),
                    policy.reserved_spend_cents_per_call,
                    str(setup_row[0]),
                    setup_row[1],
                    str(setup_row[2]),
                    setup_row[3],
                    str(setup_row[4]),
                    setup_row[5],
                    setup_row[6],
                    setup_row[7],
                    self.media_stream_url,
                ),
            )
            return self._from_row(await inserted.fetchone()), True

    async def set_status(
        self,
        tenant_id: UUID,
        request_id: UUID,
        status: OutboundCallStatus,
        *,
        call_control_id: str | None = None,
        call_leg_id: str | None = None,
        call_session_id: str | None = None,
        failure_code: str | None = None,
    ) -> OutboundCallRecord:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "UPDATE telephony_outbound_requests SET status = %s, "
                "call_control_id = COALESCE(%s, call_control_id), "
                "call_leg_id = COALESCE(%s, call_leg_id), "
                "call_session_id = COALESCE(%s, call_session_id), "
                "failure_code = %s, updated_at = NOW() WHERE tenant_id = %s::uuid "
                "AND request_id = %s::uuid RETURNING " + self._record_columns(),
                (
                    status.value,
                    call_control_id,
                    call_leg_id,
                    call_session_id,
                    failure_code,
                    str(tenant_id),
                    str(request_id),
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise KeyError(request_id)
        return self._from_row(row)
