"""Phase 28: SDK/API Surface and Versioning Strategy Test Suite."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from control_plane.app import app
from sdk.python.ucve import SDK_VERSION_MANIFEST, UCVEVoiceClient

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_28_sdk_api_surface_and_versioning_strategy.md"
)
DOCS_DIR = REPO_ROOT / "docs" / "sdk"
SDK_DIR = REPO_ROOT / "sdk"


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_flutter_roadmap_livekit_separate_self_hosted_docs() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "FLUTTER_ROADMAP" in text or "roadmap" in text.lower()
    assert "voice-livekit" in text or "@ucve/voice-livekit" in text
    assert "/docs" in text
    assert "None — fully deterministic" in text


def test_openapi_spec_syntax_and_routes() -> None:
    openapi_file = REPO_ROOT / "openapi.yaml"
    assert openapi_file.is_file()
    spec = yaml.safe_load(openapi_file.read_text(encoding="utf-8"))
    assert spec["openapi"].startswith("3.1")
    assert "/v1/session/mint" in spec["paths"]
    assert "/v1/agents" in spec["paths"]


def test_self_hosted_docs_routes_registered() -> None:
    routes = [getattr(r, "path", "") for r in app.routes if getattr(r, "path", None)]
    assert "/docs" in routes
    assert "/redoc" in routes
    assert "/openapi.json" in routes


def test_sdk_version_manifest_present() -> None:
    assert SDK_VERSION_MANIFEST["api_version"] == "1.0.0"
    assert SDK_VERSION_MANIFEST["event_schema_version"] == "1.0.0"
    assert SDK_VERSION_MANIFEST["min_server_version"] == "0.1.0"


def test_python_and_typescript_sdk_instantiate() -> None:
    # Python SDK
    client = UCVEVoiceClient(token="mock-ephemeral-token")
    assert client.token == "mock-ephemeral-token"
    assert client.version_manifest["api_version"] == "1.0.0"

    # TypeScript SDK package files
    ts_pkg = SDK_DIR / "typescript" / "package.json"
    assert ts_pkg.is_file()
    ts_meta = json.loads(ts_pkg.read_text(encoding="utf-8"))
    assert ts_meta["name"] == "@ucve/voice-sdk"


def test_sdk_constructor_rejects_raw_api_keys() -> None:
    # Zero-secret invariant: raw API keys must be rejected in constructor
    with pytest.raises(ValueError, match="Client SDK must never accept raw"):
        UCVEVoiceClient(token="mock", api_key="sk_live_123456789")

    with pytest.raises(ValueError, match="Client SDK must never accept raw"):
        UCVEVoiceClient(token="mock", secret="secret_key_123")


def test_flutter_stub_and_roadmap_exist() -> None:
    roadmap = DOCS_DIR / "FLUTTER_ROADMAP.md"
    stub = SDK_DIR / "flutter" / "lib" / "ucve_voice_client_stub.dart"
    assert roadmap.is_file()
    assert stub.is_file()
    assert "roadmap" in roadmap.read_text(encoding="utf-8").lower()


def test_livekit_package_separate_from_core_ts_build() -> None:
    core_pkg = json.loads((SDK_DIR / "typescript" / "package.json").read_text(encoding="utf-8"))
    livekit_pkg = json.loads((SDK_DIR / "typescript-livekit" / "package.json").read_text(encoding="utf-8"))

    # Core SDK must NOT require LiveKit
    assert "livekit-client" not in core_pkg.get("dependencies", {})
    # Optional package has @ucve/voice-livekit
    assert livekit_pkg["name"] == "@ucve/voice-livekit"


def test_event_schema_covers_events_and_playback_started() -> None:
    schema_file = SDK_DIR / "shared" / "event_schema.json"
    assert schema_file.is_file()
    schema = json.loads(schema_file.read_text(encoding="utf-8"))

    variants = [v.get("title") for v in schema.get("oneOf", [])]
    assert "ControlPong" in variants
    assert "ControlPlaybackStarted" in variants
    assert "ControlBargeIn" in variants
    assert "TextTurn" in variants
    assert "Transcript" in variants
    assert "MetricWaterfall" in variants


def test_mint_guide_documents_hmac_flow() -> None:
    guide = DOCS_DIR / "HOST_BACKEND_MINT_GUIDE.md"
    assert guide.is_file()
    text = guide.read_text(encoding="utf-8")
    assert "mint" in text.lower()
    assert "token" in text.lower()
    assert "zero-secret" in text.lower()


def test_versioning_policy_documents_deprecation_windows() -> None:
    versioning = DOCS_DIR / "VERSIONING.md"
    assert versioning.is_file()
    text = versioning.read_text(encoding="utf-8")
    assert "deprecation" in text.lower()
    assert "major" in text.lower()
    assert "minor" in text.lower()
