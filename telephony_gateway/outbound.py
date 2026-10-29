"""Policy-gated, idempotent creation of one outbound call."""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")


class OutboundCallError(ValueError):
    """A stable, secret-safe outbound admission or carrier error."""

    def __init__(self, code: str, *, ambiguous: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.ambiguous = ambiguous


class OutboundCallStatus(StrEnum):
    RESERVED = "reserved"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    AMBIGUOUS = "ambiguous"
    FAILED = "failed"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class CallingWindow:
    timezone: str
    start: time
    end: time

    def allows(self, instant: datetime) -> bool:
        if instant.tzinfo is None:
            raise ValueError("calling-window evaluation requires an aware timestamp")
        try:
            local = (
                instant.astimezone(ZoneInfo(self.timezone))
                .time()
                .replace(tzinfo=None)
            )
        except ZoneInfoNotFoundError as exc:
            raise OutboundCallError("invalid_calling_timezone") from exc
        if self.start == self.end:
            return False
        if self.start < self.end:
            return self.start <= local < self.end
        return local >= self.start or local < self.end


@dataclass(frozen=True, slots=True)
class OutboundCallPolicy:
    allowed_destinations: frozenset[str]
    calling_window: CallingWindow
    max_concurrent_calls: int
    max_calls_per_minute: int
    daily_spend_cap_cents: int
    reserved_spend_cents_per_call: int
    max_call_duration_seconds: int

    def __post_init__(self) -> None:
        if not self.allowed_destinations or any(
            not _E164.fullmatch(value) for value in self.allowed_destinations
        ):
            raise ValueError("allowed destinations must be non-empty E.164 values")
        positive = (
            self.max_concurrent_calls,
            self.max_calls_per_minute,
            self.daily_spend_cap_cents,
            self.reserved_spend_cents_per_call,
            self.max_call_duration_seconds,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("outbound policy limits must be positive")
        if self.reserved_spend_cents_per_call > self.daily_spend_cap_cents:
            raise ValueError("per-call spend reservation exceeds the daily cap")


@dataclass(frozen=True, slots=True)
class OutboundCallRequest:
    tenant_id: UUID
    agent_id: UUID
    destination: str
    purpose: str
    consent_reference: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class OutboundCallSetup:
    tenant_id: UUID
    agent_id: UUID
    published_version_id: UUID
    published_version: int
    did_id: UUID
    from_number: str
    trunk_id: UUID
    provider: str
    credential_ref: str
    connection_id: str
    media_stream_url: str


@dataclass(frozen=True, slots=True)
class OutboundCallRecord:
    request_id: UUID
    command_id: UUID
    request: OutboundCallRequest
    setup: OutboundCallSetup
    status: OutboundCallStatus
    requested_at: datetime
    reserved_spend_cents: int
    call_control_id: str | None = None
    call_leg_id: str | None = None
    call_session_id: str | None = None
    failure_code: str | None = None


class OutboundDialer(Protocol):
    async def dial(self, request: object) -> object: ...


class OutboundCallRepository(Protocol):
    async def reserve(
        self,
        request: OutboundCallRequest,
        policy: OutboundCallPolicy,
        now: datetime,
    ) -> tuple[OutboundCallRecord, bool]: ...

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
    ) -> OutboundCallRecord: ...


class OutboundPolicyProvider(Protocol):
    async def get_policy(self, tenant_id: UUID) -> OutboundCallPolicy: ...


class StaticOutboundPolicyProvider:
    """Explicit policy map for tests and local, non-persistent tooling."""

    def __init__(self, policies: dict[UUID, OutboundCallPolicy]) -> None:
        self._policies = dict(policies)
        self.requests: list[UUID] = []

    async def get_policy(self, tenant_id: UUID) -> OutboundCallPolicy:
        self.requests.append(tenant_id)
        try:
            return self._policies[tenant_id]
        except KeyError as exc:
            raise OutboundCallError("outbound_policy_unavailable") from exc


def _fingerprint(request: OutboundCallRequest) -> tuple[object, ...]:
    return (
        request.agent_id,
        request.destination,
        request.purpose.strip(),
        request.consent_reference.strip(),
    )


class InMemoryOutboundCallRepository:
    """Deterministic test/local repository with atomic policy enforcement."""

    def __init__(self) -> None:
        self._setups: dict[tuple[UUID, UUID], OutboundCallSetup] = {}
        self._records: dict[UUID, OutboundCallRecord] = {}
        self._keys: dict[tuple[UUID, str], UUID] = {}
        self._request_times: dict[UUID, list[datetime]] = defaultdict(list)
        self._reserved_spend: dict[UUID, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    def add_setup(self, setup: OutboundCallSetup) -> None:
        self._setups[(setup.tenant_id, setup.agent_id)] = setup

    def mark_all_terminal(self) -> None:
        self._records = {
            key: replace(value, status=OutboundCallStatus.ENDED)
            for key, value in self._records.items()
        }

    def reset_rate_window(self) -> None:
        self._request_times.clear()

    def set_reserved_spend(self, tenant_id: UUID, cents: int) -> None:
        self._reserved_spend[tenant_id] = cents

    @staticmethod
    def _validate_request(request: OutboundCallRequest) -> None:
        if not _E164.fullmatch(request.destination):
            raise OutboundCallError("invalid_destination")
        if not request.purpose.strip():
            raise OutboundCallError("purpose_required")
        if not request.consent_reference.strip():
            raise OutboundCallError("consent_required")
        if not request.idempotency_key.strip() or len(request.idempotency_key) > 255:
            raise OutboundCallError("invalid_idempotency_key")

    async def reserve(
        self,
        request: OutboundCallRequest,
        policy: OutboundCallPolicy,
        now: datetime,
    ) -> tuple[OutboundCallRecord, bool]:
        async with self._lock:
            key = (request.tenant_id, request.idempotency_key)
            existing_id = self._keys.get(key)
            if existing_id is not None:
                existing = self._records[existing_id]
                if _fingerprint(existing.request) != _fingerprint(request):
                    raise OutboundCallError("idempotency_conflict")
                return existing, False

            self._validate_request(request)
            if request.destination not in policy.allowed_destinations:
                raise OutboundCallError("destination_not_allowed")
            if not policy.calling_window.allows(now):
                raise OutboundCallError("outside_calling_window")

            setup = self._setups.get((request.tenant_id, request.agent_id))
            if setup is None:
                raise OutboundCallError("outbound_setup_unavailable")
            if setup.provider != "telnyx":
                raise OutboundCallError("outbound_provider_unavailable")
            if not (
                setup.credential_ref.strip()
                and setup.connection_id.strip()
                and _E164.fullmatch(setup.from_number)
                and setup.media_stream_url.startswith("wss://")
            ):
                raise OutboundCallError("outbound_setup_not_ready")

            active = sum(
                record.request.tenant_id == request.tenant_id
                and record.status
                in {
                    OutboundCallStatus.RESERVED,
                    OutboundCallStatus.SUBMITTING,
                    OutboundCallStatus.SUBMITTED,
                    OutboundCallStatus.AMBIGUOUS,
                }
                for record in self._records.values()
            )
            if active >= policy.max_concurrent_calls:
                raise OutboundCallError("concurrency_limit")

            cutoff = now - timedelta(minutes=1)
            recent = [
                stamp
                for stamp in self._request_times[request.tenant_id]
                if stamp > cutoff
            ]
            self._request_times[request.tenant_id] = recent
            if len(recent) >= policy.max_calls_per_minute:
                raise OutboundCallError("rate_limit")
            if (
                self._reserved_spend[request.tenant_id]
                + policy.reserved_spend_cents_per_call
                > policy.daily_spend_cap_cents
            ):
                raise OutboundCallError("spend_limit")

            record = OutboundCallRecord(
                request_id=uuid4(),
                command_id=uuid4(),
                request=request,
                setup=setup,
                status=OutboundCallStatus.RESERVED,
                requested_at=now.astimezone(UTC),
                reserved_spend_cents=policy.reserved_spend_cents_per_call,
            )
            self._records[record.request_id] = record
            self._keys[key] = record.request_id
            self._request_times[request.tenant_id].append(now)
            self._reserved_spend[request.tenant_id] += record.reserved_spend_cents
            return record, True

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
        async with self._lock:
            current = self._records[request_id]
            if current.request.tenant_id != tenant_id:
                raise KeyError(request_id)
            updated = replace(
                current,
                status=status,
                call_control_id=call_control_id or current.call_control_id,
                call_leg_id=call_leg_id or current.call_leg_id,
                call_session_id=call_session_id or current.call_session_id,
                failure_code=failure_code,
            )
            self._records[request_id] = updated
            return updated


class OutboundCallService:
    """Reserve policy atomically, then submit one idempotent Telnyx dial."""

    def __init__(
        self,
        *,
        repository: OutboundCallRepository,
        dialer: OutboundDialer,
        policy: OutboundCallPolicy | None = None,
        policy_provider: OutboundPolicyProvider | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if (policy is None) == (policy_provider is None):
            raise ValueError("configure exactly one outbound policy source")
        self.repository = repository
        self.dialer = dialer
        self.policy = policy
        self.policy_provider = policy_provider
        self.now = now or (lambda: datetime.now(UTC))

    async def create_call(self, request: OutboundCallRequest) -> OutboundCallRecord:
        policy = self.policy
        if policy is None:
            assert self.policy_provider is not None
            policy = await self.policy_provider.get_policy(request.tenant_id)
        record, created = await self.repository.reserve(request, policy, self.now())
        if not created:
            return record

        from telephony_gateway.telnyx.client import TelnyxDialRequest, TelnyxDialResult

        await self.repository.set_status(
            request.tenant_id, record.request_id, OutboundCallStatus.SUBMITTING
        )
        dial_request = TelnyxDialRequest(
            tenant_id=request.tenant_id,
            credential_ref=record.setup.credential_ref,
            to=request.destination,
            from_number=record.setup.from_number,
            connection_id=record.setup.connection_id,
            command_id=str(record.command_id),
            stream_url=record.setup.media_stream_url,
            time_limit_seconds=policy.max_call_duration_seconds,
        )
        try:
            result = await self.dialer.dial(dial_request)
            if not isinstance(result, TelnyxDialResult):
                raise OutboundCallError("invalid_carrier_response", ambiguous=True)
        except OutboundCallError as exc:
            status = (
                OutboundCallStatus.AMBIGUOUS
                if exc.ambiguous
                else OutboundCallStatus.FAILED
            )
            await self.repository.set_status(
                request.tenant_id,
                record.request_id,
                status,
                failure_code=exc.code,
            )
            raise
        return await self.repository.set_status(
            request.tenant_id,
            record.request_id,
            OutboundCallStatus.SUBMITTED,
            call_control_id=result.call_control_id,
            call_leg_id=result.call_leg_id,
            call_session_id=result.call_session_id,
        )
