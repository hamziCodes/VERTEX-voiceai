from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from telephony_gateway.outbound import (
    CallingWindow,
    InMemoryOutboundCallRepository,
    OutboundCallError,
    OutboundCallPolicy,
    OutboundCallRequest,
    OutboundCallService,
    OutboundCallSetup,
    OutboundCallStatus,
    StaticOutboundPolicyProvider,
)
from telephony_gateway.telnyx.client import (
    CredentialResolvingTelnyxDialer,
    TelnyxCallClient,
    TelnyxDialRequest,
    TelnyxDialResult,
)

TENANT_ID = uuid4()
AGENT_ID = uuid4()
DID_ID = uuid4()
VERSION_ID = uuid4()
TRUNK_ID = uuid4()
NOW = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
SOURCE = "+14155550100"
DESTINATION = "+14155550199"


class FakeDialer:
    def __init__(self) -> None:
        self.requests: list[TelnyxDialRequest] = []

    async def dial(self, request: TelnyxDialRequest) -> TelnyxDialResult:
        self.requests.append(request)
        return TelnyxDialResult(
            call_control_id="v3:test-call",
            call_leg_id="test-leg",
            call_session_id="test-session",
        )


def _setup() -> OutboundCallSetup:
    return OutboundCallSetup(
        tenant_id=TENANT_ID,
        agent_id=AGENT_ID,
        published_version_id=VERSION_ID,
        published_version=3,
        did_id=DID_ID,
        from_number=SOURCE,
        trunk_id=TRUNK_ID,
        provider="telnyx",
        credential_ref="tenant-telnyx-key",
        connection_id="connection-123",
        media_stream_url="wss://voice.example.test/v1/telephony/media",
    )


def _policy(**updates: object) -> OutboundCallPolicy:
    values: dict[str, object] = {
        "allowed_destinations": frozenset({DESTINATION}),
        "calling_window": CallingWindow(
            timezone="UTC", start=time(9, 0), end=time(17, 0)
        ),
        "max_concurrent_calls": 1,
        "max_calls_per_minute": 2,
        "daily_spend_cap_cents": 50,
        "reserved_spend_cents_per_call": 10,
        "max_call_duration_seconds": 300,
    }
    values.update(updates)
    return OutboundCallPolicy(**values)


def _request(
    *,
    destination: str = DESTINATION,
    idempotency_key: str = "outbound-request-001",
) -> OutboundCallRequest:
    return OutboundCallRequest(
        tenant_id=TENANT_ID,
        agent_id=AGENT_ID,
        destination=destination,
        purpose="appointment reminder",
        consent_reference="consent-record-42",
        idempotency_key=idempotency_key,
    )


@pytest.mark.asyncio
async def test_single_outbound_request_is_policy_gated_and_idempotent() -> None:
    repository = InMemoryOutboundCallRepository()
    repository.add_setup(_setup())
    dialer = FakeDialer()
    service = OutboundCallService(
        repository=repository,
        dialer=dialer,
        policy=_policy(),
        now=lambda: NOW,
    )

    first = await service.create_call(_request())
    second = await service.create_call(_request())

    assert first.request_id == second.request_id
    assert first.status is OutboundCallStatus.SUBMITTED
    assert first.call_control_id == "v3:test-call"
    assert len(dialer.requests) == 1
    assert dialer.requests[0].to == DESTINATION
    assert dialer.requests[0].from_number == SOURCE
    assert dialer.requests[0].connection_id == "connection-123"
    assert dialer.requests[0].command_id == str(first.command_id)
    assert dialer.requests[0].time_limit_seconds == 300


@pytest.mark.asyncio
async def test_service_resolves_policy_for_each_tenant() -> None:
    repository = InMemoryOutboundCallRepository()
    repository.add_setup(_setup())
    provider = StaticOutboundPolicyProvider({TENANT_ID: _policy()})
    service = OutboundCallService(
        repository=repository,
        dialer=FakeDialer(),
        policy_provider=provider,
        now=lambda: NOW,
    )

    result = await service.create_call(_request())

    assert result.status is OutboundCallStatus.SUBMITTED
    assert provider.requests == [TENANT_ID]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call_request", "now", "code"),
    [
        (_request(destination="+14155550200"), NOW, "destination_not_allowed"),
        (_request(), NOW.replace(hour=18), "outside_calling_window"),
        (
            OutboundCallRequest(
                tenant_id=TENANT_ID,
                agent_id=AGENT_ID,
                destination=DESTINATION,
                purpose="appointment reminder",
                consent_reference="",
                idempotency_key="missing-consent",
            ),
            NOW,
            "consent_required",
        ),
    ],
)
async def test_policy_rejects_disallowed_time_destination_and_missing_consent(
    call_request: OutboundCallRequest,
    now: datetime,
    code: str,
) -> None:
    repository = InMemoryOutboundCallRepository()
    repository.add_setup(_setup())
    service = OutboundCallService(
        repository=repository,
        dialer=FakeDialer(),
        policy=_policy(),
        now=lambda: now,
    )

    with pytest.raises(OutboundCallError, match=code):
        await service.create_call(call_request)


@pytest.mark.asyncio
async def test_concurrency_rate_spend_and_idempotency_conflicts_fail_closed() -> None:
    repository = InMemoryOutboundCallRepository()
    repository.add_setup(_setup())
    service = OutboundCallService(
        repository=repository,
        dialer=FakeDialer(),
        policy=_policy(),
        now=lambda: NOW,
    )

    await service.create_call(_request())
    with pytest.raises(OutboundCallError, match="concurrency_limit"):
        await service.create_call(_request(idempotency_key="second-call"))
    with pytest.raises(OutboundCallError, match="idempotency_conflict"):
        await service.create_call(
            _request(destination="+14155550200", idempotency_key="outbound-request-001")
        )

    repository.mark_all_terminal()
    limited_rate = OutboundCallService(
        repository=repository,
        dialer=FakeDialer(),
        policy=_policy(max_calls_per_minute=1),
        now=lambda: NOW + timedelta(seconds=1),
    )
    with pytest.raises(OutboundCallError, match="rate_limit"):
        await limited_rate.create_call(_request(idempotency_key="rate-call"))

    repository.reset_rate_window()
    repository.set_reserved_spend(TENANT_ID, 50)
    with pytest.raises(OutboundCallError, match="spend_limit"):
        await service.create_call(_request(idempotency_key="spend-call"))


@pytest.mark.asyncio
async def test_same_key_does_not_blind_redial_after_ambiguous_result() -> None:
    class AmbiguousDialer:
        def __init__(self) -> None:
            self.calls = 0

        async def dial(self, _request: TelnyxDialRequest) -> TelnyxDialResult:
            self.calls += 1
            raise OutboundCallError("carrier_result_ambiguous", ambiguous=True)

    repository = InMemoryOutboundCallRepository()
    repository.add_setup(_setup())
    dialer = AmbiguousDialer()
    service = OutboundCallService(
        repository=repository,
        dialer=dialer,
        policy=_policy(),
        now=lambda: NOW,
    )

    with pytest.raises(OutboundCallError, match="carrier_result_ambiguous"):
        await service.create_call(_request())
    replay = await service.create_call(_request())

    assert replay.status is OutboundCallStatus.AMBIGUOUS
    assert dialer.calls == 1


@pytest.mark.asyncio
async def test_telnyx_client_uses_one_command_id_and_bounded_safe_retry() -> None:
    attempts = 0
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        payloads.append(__import__("json").loads(request.content))
        if attempts == 1:
            return httpx.Response(503, json={"errors": [{"code": "temporary"}]})
        return httpx.Response(
            200,
            json={
                "data": {
                    "call_control_id": "v3:created",
                    "call_leg_id": "leg-created",
                    "call_session_id": "session-created",
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.telnyx.com"
    ) as http_client:
        client = TelnyxCallClient(
            api_key="test-only-key",
            http_client=http_client,
            max_attempts=2,
        )
        result = await client.dial(
            TelnyxDialRequest(
                to=DESTINATION,
                from_number=SOURCE,
                connection_id="connection-123",
                command_id=str(uuid4()),
                stream_url="wss://voice.example.test/v1/telephony/media",
                time_limit_seconds=300,
            )
        )

    assert result.call_control_id == "v3:created"
    assert attempts == 2
    assert payloads[0] == payloads[1]
    assert payloads[0]["stream_url"] == "wss://voice.example.test/v1/telephony/media"
    assert payloads[0]["stream_bidirectional_mode"] == "rtp"
    assert payloads[0]["stream_bidirectional_codec"] == "PCMU"


@pytest.mark.asyncio
async def test_live_dialer_gate_blocks_before_secret_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RUN_LIVE_TELEPHONY", raising=False)

    class VaultThatMustNotRun:
        async def aresolve_credential(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("credential resolution must remain gated")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: (_ for _ in ()).throw(
                AssertionError("network must remain gated")
            )
        ),
        base_url="https://api.telnyx.com",
    ) as http_client:
        dialer = CredentialResolvingTelnyxDialer(
            vault=VaultThatMustNotRun(), http_client=http_client
        )
        with pytest.raises(OutboundCallError, match="live_telephony_disabled"):
            await dialer.dial(
                TelnyxDialRequest(
                    tenant_id=TENANT_ID,
                    credential_ref="tenant-telnyx-key",
                    to=DESTINATION,
                    from_number=SOURCE,
                    connection_id="connection-123",
                    command_id=str(uuid4()),
                    stream_url="wss://voice.example.test/v1/telephony/media",
                    time_limit_seconds=300,
                )
            )


@pytest.mark.asyncio
async def test_live_dialer_resolves_byok_without_exposing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.secrets.policy import CredentialTier, ResolvedCredential

    monkeypatch.setenv("RUN_LIVE_TELEPHONY", "1")
    secret = "test-secret-never-render"
    seen_authorization = ""

    class FakeVault:
        async def aresolve_credential(
            self,
            tenant_id: str,
            provider_id: str,
            *,
            credential_ref: str | None,
            credential_type: str,
            tier: CredentialTier,
        ) -> ResolvedCredential:
            assert tenant_id == str(TENANT_ID)
            assert provider_id == "telnyx"
            assert credential_ref == "tenant-telnyx-key"
            assert credential_type == "api_key"
            assert tier is CredentialTier.BYOK
            return ResolvedCredential(
                tenant_id=tenant_id,
                provider_id=provider_id,
                credential_type=credential_type,
                requested_tier=tier,
                source_tier=tier,
                credential_ref=credential_ref,
                rotation_version=1,
                secret=secret,
            )

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_authorization
        seen_authorization = request.headers["Authorization"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "call_control_id": "v3:resolved",
                    "call_leg_id": "resolved-leg",
                    "call_session_id": "resolved-session",
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.telnyx.com"
    ) as http_client:
        dialer = CredentialResolvingTelnyxDialer(
            vault=FakeVault(), http_client=http_client
        )
        request = TelnyxDialRequest(
            tenant_id=TENANT_ID,
            credential_ref="tenant-telnyx-key",
            to=DESTINATION,
            from_number=SOURCE,
            connection_id="connection-123",
            command_id=str(uuid4()),
            stream_url="wss://voice.example.test/v1/telephony/media",
            time_limit_seconds=300,
        )
        result = await dialer.dial(request)

    assert result.call_control_id == "v3:resolved"
    assert seen_authorization == f"Bearer {secret}"
    assert secret not in repr(dialer)


def _api_key(
    client: TestClient, *, tenant_id: UUID, scopes: list[str], role: str
) -> str:
    from control_plane.app import app

    raw, _ = app.state.api_keys.generate_api_key(
        str(tenant_id),
        "outbound-test",
        scopes=scopes,
        role=role,
        subject_id="outbound-test-service",
    )
    return raw


def test_outbound_route_requires_tenant_bound_telephony_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    class RouteService:
        async def create_call(self, request: OutboundCallRequest):
            assert request.tenant_id == TENANT_ID
            assert request.agent_id == AGENT_ID
            return type(
                "Result",
                (),
                {
                    "request_id": uuid4(),
                    "status": OutboundCallStatus.SUBMITTED,
                    "call_control_id": "v3:route-call",
                },
            )()

    with TestClient(app) as client:
        app.state.outbound_call_service = RouteService()
        body = {
            "agent_id": str(AGENT_ID),
            "destination": DESTINATION,
            "purpose": "appointment reminder",
            "consent_reference": "consent-record-42",
            "idempotency_key": "route-request-001",
        }
        assert client.post("/v1/telephony/calls", json=body).status_code == 401
        denied = _api_key(
            client,
            tenant_id=TENANT_ID,
            scopes=["agent:write"],
            role="tenant_admin",
        )
        assert (
            client.post(
                "/v1/telephony/calls",
                json=body,
                headers={"Authorization": f"Bearer {denied}"},
            ).status_code
            == 403
        )
        allowed = _api_key(
            client,
            tenant_id=TENANT_ID,
            scopes=["telephony:write"],
            role="tenant_admin",
        )
        response = client.post(
            "/v1/telephony/calls",
            json=body,
            headers={"Authorization": f"Bearer {allowed}"},
        )
        assert response.status_code == 202
        assert response.json()["call_control_id"] == "v3:route-call"
        delattr(app.state, "outbound_call_service")


def test_production_runtime_is_opt_in_and_requires_secure_media_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telephony_gateway.outbound_runtime import build_outbound_runtime

    monkeypatch.delenv("UCVE_TELEPHONY_MEDIA_PUBLIC_URL", raising=False)
    assert build_outbound_runtime(object()) is None

    monkeypatch.setenv(
        "UCVE_TELEPHONY_MEDIA_PUBLIC_URL",
        "ws://voice.example.test/v1/telephony/media",
    )
    with pytest.raises(ValueError, match="wss"):
        build_outbound_runtime(object())
