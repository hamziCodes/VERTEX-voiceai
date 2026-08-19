"""Phase 21: Structured Extraction and CRM Dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_21_structured_extraction_and_crm_dispatch_contracts.md"
    )
    assert plan.is_file()


@pytest.mark.asyncio
async def test_webhook_fails_closed_without_secret() -> None:
    try:
        from post_call.webhook.dispatcher import WebhookDispatcher  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 21 implementation pending: {exc}")
    dispatcher = WebhookDispatcher()
    with pytest.raises(Exception):
        await dispatcher.dispatch(
            target_url="https://example.com/hook",
            payload={"call_id": "x"},
            secret=None,
            idempotency_key="k1",
        )
