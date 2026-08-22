"""Phase 25: Error Taxonomy & Alerting Strategy Test Suite."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from core.errors.alert_router import AlertRouter
from core.errors.client_mapper import ClientErrorMapper
from core.errors.codes import UCVEErrorCode, UCVEError
from core.errors.dlq import DeadLetterJob, DeadLetterQueueRepository
from core.errors.redaction import redact_error_details
from core.errors.structured import StructuredError
from worker_jobs.dlq_retry_sweeper import DLQRetrySweeper

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_25_error_taxonomy_and_alerting_strategy.md"
    )
    assert plan.is_file()


def test_error_codes_map_to_http_status() -> None:
    err_auth = StructuredError(code=UCVEErrorCode.AUTH_INVALID, message="Auth failed")
    assert err_auth.to_http_status() == 401

    err_quota = StructuredError(code=UCVEErrorCode.QUOTA_EXCEEDED, message="Quota exceeded")
    assert err_quota.to_http_status() == 429

    err_timeout = StructuredError(code=UCVEErrorCode.PROVIDER_TIMEOUT, message="Timeout")
    assert err_timeout.to_http_status() == 504


def test_ws_error_event_uses_generic_caller_safe_messages() -> None:
    internal_details = {"internal_db_query": "SELECT * FROM users", "phi_patient": "Jane Doe"}
    error = StructuredError(
        code=UCVEErrorCode.PROVIDER_TIMEOUT,
        message="Deep internal provider connection reset at socket 0.0.0.0",
        details=internal_details,
    )

    client_payload = ClientErrorMapper.map_to_client_payload(error)
    assert client_payload["type"] == "error"
    assert client_payload["code"] == "PROVIDER_TIMEOUT"
    # Generic message returned to caller
    assert client_payload["message"] == "We're having trouble connecting right now. Please try again."
    # No internals, stack traces, details, or correlation IDs in public WS client payload
    assert "details" not in client_payload
    assert "correlation_id" not in client_payload
    assert "Jane Doe" not in str(client_payload)


def test_error_details_redaction() -> None:
    details = {
        "user_id": "U123",
        "token": "secret_bearer_token_xyz",
        "ssn": "123-45-6789",
        "nested": {"password": "pass123", "normal": "val"},
    }
    redacted = redact_error_details(details)
    assert redacted["user_id"] == "U123"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["ssn"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["normal"] == "val"


@pytest.mark.asyncio
async def test_dlq_retention_and_retry_sweeper() -> None:
    repo = DeadLetterQueueRepository()
    tenant_id = uuid4()

    # Enqueue failed job
    job = repo.enqueue(tenant_id, "post_call_dispatch", "call_123", UCVEErrorCode.DISPATCH_FAILED)
    assert job.attempts == 1
    assert (job.expires_at - job.created_at).days == 30  # 30-day TTL

    sweeper = DLQRetrySweeper(repo)
    res = await sweeper.run_sweep()
    assert res["retried"] == 1
    assert job.attempts == 2

    # Run sweeper until max attempts reached (max 3)
    await sweeper.run_sweep()
    assert job.attempts == 3

    # Subsequent sweeps should not retry (attempts >= max_attempts)
    res3 = await sweeper.run_sweep()
    assert res3["retried"] == 0


@pytest.mark.asyncio
async def test_dlq_purge_expired_items() -> None:
    repo = DeadLetterQueueRepository()
    tenant_id = uuid4()

    job = repo.enqueue(tenant_id, "post_call_dispatch", "call_456", UCVEErrorCode.EXTRACTION_FAILED)
    # Expire job artificially past 30 days
    job.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    sweeper = DLQRetrySweeper(repo)
    res = await sweeper.run_sweep()
    assert res["purged"] == 1


@pytest.mark.asyncio
async def test_alert_router_routes_by_severity() -> None:
    router = AlertRouter()
    tenant_id = uuid4()

    error = StructuredError(
        code=UCVEErrorCode.QUOTA_EXCEEDED,
        message="Quota soft warning at 80% capacity",
        severity="warn",
    )

    await router.route_alert(tenant_id, error, alert_webhook_url="https://tenant.com/alert-webhook")
    assert len(router.routed_alerts) == 1
    assert router.routed_alerts[0]["webhook_dispatched"] is True
