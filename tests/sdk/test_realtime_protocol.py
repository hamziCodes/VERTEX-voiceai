"""Phase 05 realtime protocol and Python SDK contract tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from core.protocol.realtime import (
    PROTOCOL_VERSION,
    ProtocolCompatibilityError,
    build_event,
    negotiate_protocol,
)
from sdk.python.ucve.client import UCVEVoiceClient
from worker_raw.security.ws_policy import (
    WSSecurityViolation,
    validate_demo_provider_overrides,
)

ROOT = Path(__file__).resolve().parents[2]


def test_canonical_event_envelope_is_versioned_ordered_and_identified() -> None:
    first = build_event("control.ping", {"interval_sec": 20}, sequence=1)
    second = build_event("control.pong", {}, sequence=2)

    assert first["protocol_version"] == PROTOCOL_VERSION
    assert first["event_id"] != second["event_id"]
    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert first["payload"] == {"interval_sec": 20}


def test_protocol_negotiation_accepts_same_major_and_rejects_other_major() -> None:
    result = negotiate_protocol("1.7.2")
    assert result.protocol_version == PROTOCOL_VERSION
    assert result.client_version == "1.7.2"

    with pytest.raises(ProtocolCompatibilityError) as exc_info:
        negotiate_protocol("2.0.0")

    assert exc_info.value.code == "PROTOCOL_VERSION_UNSUPPORTED"
    assert exc_info.value.supported_range == ">=1.0.0 <2.0.0"


def test_shared_schema_declares_handshake_lifecycle_and_direction() -> None:
    schema = json.loads((ROOT / "sdk/shared/event_schema.json").read_text("utf-8"))
    assert schema["protocol_version"] == PROTOCOL_VERSION
    assert schema["supported_range"] == ">=1.0.0 <2.0.0"
    names = {item["properties"]["event_type"]["const"] for item in schema["oneOf"]}
    assert {
        "protocol.hello",
        "session.ready",
        "control.ping",
        "control.pong",
        "session.token_expiring",
        "session.close",
        "error",
        "degraded",
    } <= names
    assert all("x-direction" in item for item in schema["oneOf"])


def test_python_client_url_encodes_token_and_gates_demo_overrides() -> None:
    client = UCVEVoiceClient("token +/?&= value", ws_url="ws://localhost/ws/audio?x=1")
    url = client.connection_url

    assert "token=token+%2B%2F%3F%26%3D+value" in url
    assert "protocol_version=1.0.0" in url
    assert "stt_provider" not in url

    demo = UCVEVoiceClient(
        "token",
        demo_provider_overrides={"stt_provider": "gladia"},
        allow_demo_provider_overrides=True,
    )
    assert "stt_provider=gladia" in demo.connection_url

    with pytest.raises(ValueError, match="demo-only"):
        UCVEVoiceClient("token", demo_provider_overrides={"llm_provider": "groq"})


def test_python_client_builds_canonical_hello_and_text_turn() -> None:
    client = UCVEVoiceClient("token")
    hello = client.build_hello_event()
    turn = client.build_text_turn(" hello ")

    assert hello["event_type"] == "protocol.hello"
    assert hello["payload"]["protocol_version"] == PROTOCOL_VERSION
    assert hello["payload"]["sdk"]["name"] == "ucve-python"
    assert turn["event_type"] == "text.turn"
    assert turn["payload"]["text"] == "hello"
    assert turn["sequence"] > hello["sequence"]


def test_python_client_rejects_empty_text_turn() -> None:
    with pytest.raises(ValueError, match="text is required"):
        UCVEVoiceClient("token").build_text_turn("   ")


@pytest.mark.asyncio
async def test_python_client_retries_failed_handshake_and_closes_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSocket:
        def __init__(self, ready: dict[str, Any] | Exception) -> None:
            self.ready = ready
            self.closed = False

        async def send(self, _value: str) -> None:
            return None

        async def recv(self) -> str:
            if isinstance(self.ready, Exception):
                raise self.ready
            return json.dumps(self.ready)

        async def close(self) -> None:
            self.closed = True

    first = FakeSocket(ConnectionError("negotiation interrupted"))
    second = FakeSocket(
        {
            "event_type": "session.ready",
            "payload": {"protocol_version": PROTOCOL_VERSION},
        }
    )
    sockets = [first, second]

    async def fake_connect(_url: str) -> FakeSocket:
        return sockets.pop(0)

    monkeypatch.setattr("sdk.python.ucve.client.websockets.connect", fake_connect)
    client = UCVEVoiceClient(
        "token",
        max_connect_attempts=2,
        reconnect_backoff_sec=0,
    )

    await client.connect()

    assert client._running is True
    assert first.closed is True
    assert sockets == []
    await client.disconnect()
    assert second.closed is True


def test_roadmap_clients_cannot_be_mistaken_for_v1_packages() -> None:
    livekit = json.loads(
        (ROOT / "sdk/typescript-livekit/package.json").read_text("utf-8")
    )
    flutter = (ROOT / "sdk/flutter/ROADMAP.md").read_text("utf-8").lower()

    assert livekit["private"] is True
    assert livekit["name"] == "@ucve/voice-livekit"
    assert "roadmap-only" in livekit["description"].lower()
    assert "roadmap" in flutter and "not" in flutter and "v1" in flutter


def test_python_distribution_uses_installable_top_level_namespace() -> None:
    pyproject = (ROOT / "sdk/python/pyproject.toml").read_text("utf-8")
    assert 'packages = ["ucve"]' in pyproject
    assert (ROOT / "sdk/python/README.md").is_file()
    client_source = (ROOT / "sdk/python/ucve/client.py").read_text("utf-8")
    assert "from .version import" in client_source


def test_typescript_core_and_react_exports_are_separate() -> None:
    package = json.loads((ROOT / "sdk/typescript/package.json").read_text("utf-8"))
    core_index = (ROOT / "sdk/typescript/src/index.ts").read_text("utf-8")
    react_index = (ROOT / "sdk/typescript/src/react.ts").read_text("utf-8")

    assert "./react" in package["exports"]
    assert "./hooks/useUCVEVoice" not in core_index
    assert "./hooks/useUCVEVoice" in react_index
    assert package["files"] == ["dist", "README.md"]


def test_react_hook_exposes_audio_send_cancel_and_preserves_callbacks() -> None:
    hook = (ROOT / "sdk/typescript/src/hooks/useUCVEVoice.ts").read_text("utf-8")
    assert "sendAudioChunk" in hook
    assert "cancelPlayback" in hook
    assert "options.onTranscript?.(speaker, text)" in hook
    assert "options.onClose?.(" in hook
    assert "return () =>" in hook


def test_provider_overrides_require_explicit_local_demo_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overrides = {"stt_provider": "gladia"}
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.setenv("UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES", "1")
    with pytest.raises(WSSecurityViolation, match="PROVIDER_OVERRIDE_FORBIDDEN"):
        validate_demo_provider_overrides(overrides)

    monkeypatch.setenv("UCVE_ENV", "development")
    monkeypatch.setenv("UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES", "0")
    with pytest.raises(WSSecurityViolation, match="PROVIDER_OVERRIDE_FORBIDDEN"):
        validate_demo_provider_overrides(overrides)

    monkeypatch.setenv("UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES", "1")
    assert validate_demo_provider_overrides(overrides) == overrides


def test_protocol_documentation_is_generated_from_schema() -> None:
    generator_path = ROOT / "sdk/shared/generate_protocol_docs.py"
    spec = importlib.util.spec_from_file_location("protocol_docs", generator_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schema = json.loads((ROOT / "sdk/shared/event_schema.json").read_text("utf-8"))
    documented = (ROOT / "docs/sdk/REALTIME_PROTOCOL.md").read_text("utf-8")
    assert documented == module.render_protocol_document(schema)


def test_host_backend_example_uses_authenticated_hmac_mint_contract() -> None:
    example = (ROOT / "examples/host-backend/app.py").read_text("utf-8")
    assert 'f"{UCVE_CONTROL_PLANE}/v1/session"' in example
    assert '"X-Timestamp"' in example
    assert '"X-Nonce"' in example
    assert '"X-Agent-Id"' in example
    assert '"X-Signature"' in example
    assert "/v1/session/mint" not in example


def test_python_and_typescript_protocol_types_are_generated_from_schema() -> None:
    generator_path = ROOT / "sdk/shared/generate_protocol_types.py"
    spec = importlib.util.spec_from_file_location("protocol_types", generator_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schema = json.loads((ROOT / "sdk/shared/event_schema.json").read_text("utf-8"))

    assert (ROOT / "sdk/python/ucve/protocol_generated.py").read_text(
        "utf-8"
    ) == module.render_python(schema)
    assert (ROOT / "sdk/typescript/src/protocol.generated.ts").read_text(
        "utf-8"
    ) == module.render_typescript(schema)
