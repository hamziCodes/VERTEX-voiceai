from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from core.db.repos.telephony_repo import InMemoryTelephonyRepository
from telephony_gateway.main import app
from telephony_gateway.telnyx.signature import verify_telnyx_signature
from telephony_gateway.telnyx.webhook import (
    InMemoryTelnyxEventSink,
    TelnyxWebhookService,
    build_telnyx_webhook_service,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "telephony"
    / "telnyx_call_initiated.json"
)
NOW = 1_793_095_200


@pytest.fixture
def signed_client() -> tuple[TestClient, Ed25519PrivateKey, InMemoryTelnyxEventSink]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes_raw()
    sink = InMemoryTelnyxEventSink()
    app.state.telnyx_webhook_service = TelnyxWebhookService(
        public_key=base64.b64encode(public_key).decode("ascii"),
        event_sink=sink,
        now=lambda: float(NOW),
    )
    with TestClient(app) as client:
        yield client, private_key, sink
    app.state.telnyx_webhook_service = None


def _headers(
    private_key: Ed25519PrivateKey, body: bytes, timestamp: str
) -> dict[str, str]:
    signature = private_key.sign(timestamp.encode("ascii") + b"|" + body)
    return {
        "content-type": "application/json",
        "telnyx-timestamp": timestamp,
        "telnyx-signature-ed25519": base64.b64encode(signature).decode("ascii"),
    }


def test_valid_exact_raw_body_is_accepted_once(signed_client) -> None:
    client, private_key, sink = signed_client
    body = FIXTURE.read_bytes()
    headers = _headers(private_key, body, str(NOW))

    first = client.post("/v1/telephony/webhooks/telnyx", content=body, headers=headers)
    duplicate = client.post(
        "/v1/telephony/webhooks/telnyx", content=body, headers=headers
    )

    assert first.status_code == 202
    assert first.json() == {
        "status": "accepted",
        "event_id": "11111111-1111-4111-8111-111111111111",
        "event_type": "call.initiated",
    }
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "duplicate"
    assert len(sink.events) == 1


@pytest.mark.parametrize(
    ("timestamp", "signature"),
    [
        (None, None),
        (str(NOW - 301), "invalid"),
        (str(NOW + 301), "invalid"),
        ("nan", "invalid"),
        ("not-a-timestamp", "invalid"),
    ],
)
def test_missing_stale_future_and_malformed_auth_are_rejected(
    signed_client, timestamp: str | None, signature: str | None
) -> None:
    client, _private_key, sink = signed_client
    headers = {"content-type": "application/json"}
    if timestamp is not None:
        headers["telnyx-timestamp"] = timestamp
    if signature is not None:
        headers["telnyx-signature-ed25519"] = signature

    response = client.post(
        "/v1/telephony/webhooks/telnyx",
        content=FIXTURE.read_bytes(),
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_telnyx_signature"
    assert sink.events == {}


def test_tampering_and_json_reserialization_are_rejected(signed_client) -> None:
    client, private_key, sink = signed_client
    body = FIXTURE.read_bytes()
    headers = _headers(private_key, body, str(NOW))
    parsed = json.loads(body)
    reserialized = json.dumps(parsed, indent=2).encode("utf-8")

    assert (
        client.post(
            "/v1/telephony/webhooks/telnyx", content=reserialized, headers=headers
        ).status_code
        == 401
    )
    assert sink.events == {}


@pytest.mark.parametrize("mutation", ["unknown", "missing_call_id", "bad_json"])
def test_verified_but_unsupported_or_malformed_payload_is_rejected(
    signed_client, mutation: str
) -> None:
    client, private_key, sink = signed_client
    payload = json.loads(FIXTURE.read_bytes())
    if mutation == "unknown":
        payload["data"]["event_type"] = "call.unrecognized"
        body = json.dumps(payload, separators=(",", ":")).encode()
    elif mutation == "missing_call_id":
        del payload["data"]["payload"]["call_control_id"]
        body = json.dumps(payload, separators=(",", ":")).encode()
    else:
        body = b"{not-json"
    headers = _headers(private_key, body, str(NOW))

    response = client.post(
        "/v1/telephony/webhooks/telnyx", content=body, headers=headers
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_telnyx_event"
    assert sink.events == {}


def test_unsigned_legacy_route_and_unconfigured_canonical_route_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TELNYX_PUBLIC_KEY", raising=False)
    app.state.telnyx_webhook_service = None
    app.state.telnyx_event_sink = None
    with TestClient(app) as client:
        assert (
            client.post(
                "/v1/telephony/webhook/telnyx", content=FIXTURE.read_bytes()
            ).status_code
            == 404
        )
        response = client.post(
            "/v1/telephony/webhooks/telnyx", content=FIXTURE.read_bytes()
        )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "telnyx_verifier_unavailable"


def test_production_verifier_never_accepts_hmac_mode() -> None:
    assert (
        verify_telnyx_signature(
            FIXTURE.read_bytes(),
            "not-an-ed25519-signature",
            str(NOW),
            hmac_secret="test-only-secret",
            now=float(NOW),
        )
        is False
    )


def test_service_factory_fails_closed_without_public_key(monkeypatch) -> None:
    monkeypatch.delenv("TELNYX_PUBLIC_KEY", raising=False)
    with pytest.raises(ValueError, match="TELNYX_PUBLIC_KEY"):
        build_telnyx_webhook_service(event_sink=InMemoryTelnyxEventSink())


def test_verified_event_with_unknown_did_fails_closed() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = base64.b64encode(private_key.public_key().public_bytes_raw()).decode(
        "ascii"
    )
    app.state.telnyx_webhook_service = TelnyxWebhookService(
        public_key=public_key,
        event_sink=InMemoryTelephonyRepository(),
        now=lambda: float(NOW),
    )
    body = FIXTURE.read_bytes()
    with TestClient(app) as client:
        response = client.post(
            "/v1/telephony/webhooks/telnyx",
            content=body,
            headers=_headers(private_key, body, str(NOW)),
        )
    app.state.telnyx_webhook_service = None

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "telnyx_call_not_admitted"


@pytest.mark.parametrize(
    "bad_key",
    ["qualification-placeholder", "c2hvcnQ=", "!!!not-base64!!!"],
)
def test_malformed_public_key_fails_at_startup_not_on_first_webhook(bad_key: str) -> None:
    """Regression (Phase 15): a placeholder key made the gateway report the
    verifier as configured while every real webhook would fail."""
    from telephony_gateway.telnyx.webhook import (
        InMemoryTelnyxEventSink,
        build_telnyx_webhook_service,
    )

    with pytest.raises(ValueError, match="TELNYX_PUBLIC_KEY must be"):
        build_telnyx_webhook_service(event_sink=InMemoryTelnyxEventSink(), public_key=bad_key)
