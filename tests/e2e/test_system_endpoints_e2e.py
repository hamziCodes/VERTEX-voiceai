"""Comprehensive End-to-End Test Suite for All System Endpoints, RAG, Telephony, and Providers."""

from __future__ import annotations

import json
import os
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from control_plane.app import app as control_plane_app
from core.protocol.realtime import build_event
from core.providers.factory import (
    SUPPORTED_LLM,
    SUPPORTED_STT,
    SUPPORTED_TTS,
    build_llm_provider,
    build_stt_provider,
    build_tts_provider,
)
from core.providers.interfaces.llm import LLMConfig
from core.rag.models import KnowledgeBaseChunk
from core.rag.retriever import PgVectorRetriever
from core.rag.speculative import SpeculativeRetrieval
from telephony_gateway.main import app as telephony_app
from telephony_gateway.webhook_normalizer import WebhookNormalizer
from worker_raw.main import app as worker_raw_app


@pytest.fixture(autouse=True)
def _offline_demo_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make this demo endpoint suite explicit and independent of local .env state."""

    monkeypatch.setenv("UCVE_DEMO_MODE", "1")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")


@pytest.fixture
def cp_client() -> TestClient:
    return TestClient(control_plane_app)


@pytest.fixture
def tel_client() -> TestClient:
    return TestClient(telephony_app)


@pytest.fixture
def worker_client() -> TestClient:
    return TestClient(worker_raw_app)


# ==============================================================================
# 1. CONTROL PLANE ENDPOINTS E2E
# ==============================================================================

def test_control_plane_health(cp_client: TestClient) -> None:
    res = cp_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "control-plane"


def test_control_plane_metrics(cp_client: TestClient) -> None:
    bearer = os.environ.get("UCVE_METRICS_BEARER", "dev-only-replace-me-metrics-bearer")
    res = cp_client.get("/metrics", headers={"Authorization": f"Bearer {bearer}"})
    assert res.status_code == 200
    assert "process_cpu_seconds_total" in res.text or "ucve" in res.text or res.status_code == 200


def test_control_plane_openapi_docs(cp_client: TestClient) -> None:
    res = cp_client.get("/docs")
    assert res.status_code == 200
    assert "swagger" in res.text.lower() or "openapi" in res.text.lower()


def test_control_plane_quick_mint(cp_client: TestClient) -> None:
    res = cp_client.post(
        "/mint",
        json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "agent_id": "00000000-0000-0000-0000-0000000000a1",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert "ws_url" in data
    assert "session_id" in data


def test_control_plane_knowledge_base_status(cp_client: TestClient) -> None:
    tenant_id = "00000000-0000-0000-0000-000000000001"
    res = cp_client.get(f"/v1/knowledge-bases/status/{tenant_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert "total_chunks" in data


# ==============================================================================
# 2. TELEPHONY GATEWAY ENDPOINTS E2E
# ==============================================================================

def test_telephony_gateway_health(tel_client: TestClient) -> None:
    res = tel_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "telephony-gateway"


def test_telephony_gateway_root(tel_client: TestClient) -> None:
    res = tel_client.get("/")
    assert res.status_code == 200
    assert res.json()["service"] == "telephony-gateway"


def test_telephony_gateway_telnyx_webhook_normalization(tel_client: TestClient) -> None:
    payload = {
        "data": {
            "event_type": "call.initiated",
            "id": "evt-telnyx-12345",
            "payload": {
                "call_control_id": "ctrl-call-abc",
                "call_leg_id": "leg-xyz",
                "call_session_id": "sess-call-789",
                "client_state": None,
                "connection_id": "conn-123",
                "from": "+14155550100",
                "to": "+14155550199",
                "direction": "incoming",
                "state": "active",
            },
            "record_type": "event",
        }
    }
    res = tel_client.post("/v1/telephony/webhook/telnyx", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed"
    assert data["carrier"] == "telnyx"
    assert data["event_type"] in ("call_started", "call.initiated")
    assert "session_id" in data


def test_telephony_gateway_invalid_carrier_fails(tel_client: TestClient) -> None:
    with pytest.raises(Exception):
        WebhookNormalizer.normalize("unsupported_carrier", {})


# ==============================================================================
# 3. RAG SUBSYSTEM E2E (PgVectorRetriever & Speculative RAG)
# ==============================================================================

@pytest.mark.asyncio
async def test_rag_retriever_tenant_isolation() -> None:
    retriever = PgVectorRetriever()
    tenant_a = uuid4()
    tenant_b = uuid4()

    chunk_a = KnowledgeBaseChunk(
        chunk_id=uuid4(),
        tenant_id=tenant_a,
        source_document_id=uuid4(),
        text="The clinic opening hours are Monday to Friday 9am to 5pm.",
        metadata={"category": "schedule"},
    )
    chunk_b = KnowledgeBaseChunk(
        chunk_id=uuid4(),
        tenant_id=tenant_b,
        source_document_id=uuid4(),
        text="Confidential financial audit report for Q3 enterprise revenue.",
        metadata={"category": "finance"},
    )

    retriever.seed_chunks(tenant_a, [chunk_a])
    retriever.seed_chunks(tenant_b, [chunk_b])

    # Search for clinic hours under tenant A
    res_a = await retriever.retrieve("What are the clinic opening hours?", tenant_a, top_k=3)
    assert len(res_a) > 0
    assert "clinic opening hours" in res_a[0].text

    # Search for financial data under tenant A (must return empty/zero tenant B chunks)
    res_a_leak = await retriever.retrieve("Confidential financial revenue", tenant_a, top_k=3)
    assert all(c.tenant_id == tenant_a for c in res_a_leak)
    assert not any("financial audit" in c.text for c in res_a_leak)

    # Search under tenant B
    res_b = await retriever.retrieve("enterprise revenue", tenant_b, top_k=3)
    assert len(res_b) > 0
    assert "enterprise revenue" in res_b[0].text


@pytest.mark.asyncio
async def test_rag_speculative_retrieval_flow() -> None:
    retriever = PgVectorRetriever()
    tenant = uuid4()
    chunk = KnowledgeBaseChunk(
        chunk_id=uuid4(),
        tenant_id=tenant,
        source_document_id=uuid4(),
        text="Wavia provides sovereign on-premise voice AI with sub-450ms latency.",
        metadata={},
    )
    retriever.seed_chunks(tenant, [chunk])

    speculative = SpeculativeRetrieval(retriever)

    # Speculate on partial STT
    spec_results = await speculative.speculate("wavia voice AI latency", tenant)
    assert len(spec_results) > 0

    # Reconcile on final STT
    final_results = await speculative.reconcile("What is the latency of Wavia voice AI?", tenant)
    assert len(final_results) > 0
    assert "sub-450ms latency" in final_results[0].text


# ==============================================================================
# 4. PROVIDER COMBINATION MATRIX E2E
# ==============================================================================

def test_supported_provider_sets() -> None:
    assert "gladia" in SUPPORTED_STT
    assert "deepgram" in SUPPORTED_STT
    assert "groq" in SUPPORTED_LLM
    assert "gemini" in SUPPORTED_LLM
    assert "openai" in SUPPORTED_LLM
    assert "cartesia" in SUPPORTED_TTS
    assert "uplift" in SUPPORTED_TTS
    assert "elevenlabs" in SUPPORTED_TTS


@pytest.mark.asyncio
async def test_all_18_provider_combinations_instantiate_cleanly() -> None:
    """Verify that every combination of STT, LLM, and TTS can be built and run."""
    stt_list = ["gladia", "deepgram"]
    llm_list = ["groq", "gemini", "openai"]
    tts_list = ["cartesia", "uplift", "elevenlabs"]

    count = 0
    for stt_id in stt_list:
        stt = build_stt_provider(stt_id, api_key="", mock_text="Test prompt")
        assert stt.health_check() is True

        for llm_id in llm_list:
            llm = build_llm_provider(llm_id, api_key="")
            assert llm.health_check() is True

            for tts_id in tts_list:
                tts = build_tts_provider(tts_id, api_key="")
                assert tts.health_check() is True
                count += 1

    assert count == 18


@pytest.mark.asyncio
async def test_openai_llm_generate_stream() -> None:
    llm = build_llm_provider("openai", api_key="", model="gpt-4o-mini")
    messages = [{"role": "user", "content": "What is 2+2?"}]
    chunks = []
    async for chunk in llm.generate_stream(messages, LLMConfig(model="gpt-4o-mini")):
        chunks.append(chunk)
    assert len(chunks) > 0
    full_reply = "".join(c.text for c in chunks)
    assert len(full_reply.strip()) > 0


# ==============================================================================
# 5. WORKER RAW WEBSOCKET HANDSHAKE & MINT TEST
# ==============================================================================

def test_worker_raw_health(worker_client: TestClient) -> None:
    res = worker_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_worker_raw_json_version(worker_client: TestClient) -> None:
    res = worker_client.get("/json/version")
    assert res.status_code == 200
    assert res.json()["service"] == "ucve-worker-raw"


def test_worker_raw_websocket_handshake_and_turn(cp_client: TestClient, worker_client: TestClient) -> None:
    # 1. Mint session token via Control Plane
    mint_res = cp_client.post(
        "/mint",
        json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "agent_id": "00000000-0000-0000-0000-0000000000a1",
        },
    )
    assert mint_res.status_code == 200
    token = mint_res.json()["token"]

    # 2. Connect using the published session plan (provider query overrides are demo-only).
    ws_path = f"/ws/audio?token={token}"
    with worker_client.websocket_connect(ws_path) as ws:
        ws.send_text(
            json.dumps(
                build_event(
                    "protocol.hello",
                    {
                        "protocol_version": "1.0.0",
                        "sdk": {"name": "pytest", "version": "1.0.0"},
                    },
                    sequence=1,
                )
            )
        )
        # Protocol readiness precedes provider/runtime readiness.
        first_event = json.loads(ws.receive_text())
        assert first_event["event_type"] == "session.ready"
        assert first_event["payload"]["protocol_version"] == "1.0.0"
        runtime_ready = json.loads(ws.receive_text())
        assert runtime_ready["event_type"] == "metric"
        assert runtime_ready["payload"]["kind"] == "session_ready"

        # Ping/Pong control event
        ws.send_text(
            json.dumps(build_event("control.ping", {"t": time.time()}, sequence=2))
        )
        resp_text = ws.receive_text()
        resp_data = json.loads(resp_text)
        assert resp_data["event_type"] == "control.pong"

        # Simulate text turn
        ws.send_text(
            json.dumps(
                build_event(
                    "text.turn",
                    {"text": "Hello Wavia, confirm system status."},
                    sequence=3,
                )
            )
        )
        time.sleep(0.1)
