"""Offline Phase 04 teardown ownership tests."""

from __future__ import annotations

import asyncio

import pytest

from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig
from worker_raw.ws_session import WebSocketSessionRunner


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_runtime_shutdown_cancels_owned_tasks_and_closes_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)
    orchestrator = PipelineOrchestrator()

    async def hanging() -> None:
        await asyncio.Event().wait()

    tasks = [asyncio.create_task(hanging()) for _ in range(4)]
    orchestrator._llm_task = tasks[0]
    orchestrator._tts_task = tasks[1]
    orchestrator._barge_verify_task = tasks[2]
    orchestrator._egress_sender_task = tasks[3]
    providers = [_Closable(), _Closable(), _Closable()]
    (
        orchestrator.llm_provider,
        orchestrator.tts_provider,
        orchestrator.stt_provider,
    ) = providers

    await orchestrator.shutdown_runtime_resources()

    assert all(task.done() for task in tasks)
    assert all(provider.closed for provider in providers)
    assert orchestrator.runtime_task_count == 0


@pytest.mark.asyncio
async def test_runtime_shutdown_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)
    orchestrator = PipelineOrchestrator()
    orchestrator.llm_provider = _Closable()
    orchestrator.tts_provider = _Closable()
    orchestrator.stt_provider = _Closable()

    await orchestrator.shutdown_runtime_resources()
    await orchestrator.shutdown_runtime_resources()

    assert orchestrator.runtime_task_count == 0


class _StartupFailureOrchestrator:
    def __init__(self) -> None:
        from core.fsm.barge_in import BargeInController
        from core.fsm.cancel_contract import ThreePointCancel
        from core.fsm.session_fsm import SessionFSM

        self.barge_in_controller = BargeInController()
        self.three_point_cancel = ThreePointCancel()
        self.fsm = SessionFSM()
        self.vad_adapter = type("VAD", (), {"reset": lambda _self: None})()
        self.finalized = False

    def attach_ws_session(self, _session: object) -> None:
        return None

    async def apply_provider_selection(self, _config: PipelineSessionConfig) -> None:
        return None

    def apply_language_vad_overrides(self, _language: str) -> None:
        return None

    async def prepare_live_stt(self) -> str:
        raise RuntimeError("startup failed")

    async def finalize_session(self, _config: PipelineSessionConfig) -> None:
        self.finalized = True


class _StartupSocket:
    def __init__(self) -> None:
        self.closed = False

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


class _StartupTransport:
    def __init__(self) -> None:
        self.closed = False

    async def close(self, websocket: _StartupSocket) -> None:
        self.closed = True
        await websocket.close()


@pytest.mark.asyncio
async def test_startup_failure_still_finalizes_and_closes_transport() -> None:
    websocket = _StartupSocket()
    transport = _StartupTransport()
    orchestrator = _StartupFailureOrchestrator()
    released = False

    async def release() -> None:
        nonlocal released
        released = True

    config = PipelineSessionConfig(session_id="s", tenant_id="t", agent_id="a")
    runner = WebSocketSessionRunner(
        websocket,
        transport,  # type: ignore[arg-type]
        orchestrator,  # type: ignore[arg-type]
        config,
        release_admission=release,
    )

    with pytest.raises(RuntimeError, match="startup failed"):
        await runner.start()

    assert orchestrator.finalized is True
    assert transport.closed is True
    assert websocket.closed is True
    assert released is True
