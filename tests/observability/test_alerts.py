"""Phase 14: alerts are durable, de-duplicated, honestly delivered and wired."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import yaml

from core.alerts.models import AlertCode, AlertSeverity, sanitize_facts
from core.alerts.repository import InMemoryAlertRepository
from core.alerts.service import (
    SIGNATURE_HEADER,
    AlertService,
    AlertWebhookNotifier,
    notifier_from_environment,
    set_process_alert_service,
)
from core.observability.metrics import get_metrics_registry, ucve_alerts_total

REPO = Path(__file__).resolve().parents[2]
SECRET = "test-alert-secret-0123456789"


def _service(handler=None) -> AlertService:
    notifier = None
    if handler is not None:
        notifier = AlertWebhookNotifier(
            "https://alerts.example/hook",
            SECRET,
            transport=httpx.MockTransport(handler),
        )
    return AlertService(InMemoryAlertRepository(), notifier)


async def _raise(service: AlertService, severity=AlertSeverity.WARNING, **extra):
    return await service.raise_alert(
        alert_key=extra.pop("key", "quota_soft_cap:t1:2026-11"),
        code=extra.pop("code", AlertCode.QUOTA_SOFT_CAP),
        severity=severity,
        summary="Usage passed the soft warning threshold for this month.",
        **extra,
    )


@pytest.mark.asyncio
async def test_repeats_are_deduplicated_and_counted() -> None:
    service = _service()
    before = ucve_alerts_total.labels(code="QUOTA_SOFT_CAP", severity="warning").value
    first = await _raise(service)
    second = await _raise(service)
    assert first.is_new and not second.is_new
    assert second.alert.alert_id == first.alert.alert_id
    assert second.alert.occurrences == 2
    assert second.delivery == "deduplicated"
    after = ucve_alerts_total.labels(code="QUOTA_SOFT_CAP", severity="warning").value
    assert after == before + 1


@pytest.mark.asyncio
async def test_escalation_notifies_again_and_resolution_reopens_fresh() -> None:
    service = _service()
    await _raise(service, key="capacity:x", code=AlertCode.CAPACITY_EXHAUSTED)
    escalated = await _raise(
        service,
        AlertSeverity.CRITICAL,
        key="capacity:x",
        code=AlertCode.CAPACITY_EXHAUSTED,
    )
    assert escalated.escalated and escalated.alert.severity is AlertSeverity.CRITICAL
    assert await service.resolve("capacity:x")
    reopened = await _raise(
        service, key="capacity:x", code=AlertCode.CAPACITY_EXHAUSTED
    )
    assert reopened.is_new and reopened.alert.alert_id != escalated.alert.alert_id


@pytest.mark.asyncio
async def test_no_channel_is_recorded_as_not_configured() -> None:
    service = _service()
    raised = await _raise(service)
    assert raised.delivery == "not_configured"
    stored = (await service.repository.list_alerts())[0]
    assert stored.delivery_status == "not_configured"


@pytest.mark.asyncio
async def test_webhook_is_signed_and_delivery_is_honest() -> None:
    received: list[httpx.Request] = []

    def ok(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(204)

    raised = await _raise(_service(ok))
    assert raised.delivery == "delivered"
    request = received[0]
    signature = request.headers[SIGNATURE_HEADER]
    match = re.fullmatch(r"t=(\d+),v1=([0-9a-f]{64})", signature)
    assert match
    expected = hmac.new(
        SECRET.encode(), f"{match.group(1)}.".encode() + request.content, hashlib.sha256
    ).hexdigest()
    assert hmac.compare_digest(expected, match.group(2))
    body = json.loads(request.content)
    assert body["type"] == "alert.raised"
    assert body["alert"]["code"] == "QUOTA_SOFT_CAP"

    failed = await _raise(
        _service(lambda r: httpx.Response(500)), key="quota_soft_cap:t2:2026-11"
    )
    assert failed.delivery == "failed"

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    down = await _raise(_service(unreachable), key="quota_soft_cap:t3:2026-11")
    assert down.delivery == "failed"


def test_facts_cannot_carry_content_or_identifiers() -> None:
    facts = sanitize_facts(
        {
            "period": "2026-11",
            "max_sessions": 5,
            "caller": "+44 7700 900123",
            "transcript": "hello there my card number is",
            "email": "a@b.example",
            "ok": True,
        }
    )
    assert facts == {"period": "2026-11", "max_sessions": 5, "ok": True}


def test_webhook_configuration_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WAVIA_ALERT_WEBHOOK_URL", raising=False)
    assert notifier_from_environment() is None
    monkeypatch.setenv("WAVIA_ALERT_WEBHOOK_URL", "https://alerts.example/hook")
    monkeypatch.delenv("WAVIA_ALERT_WEBHOOK_SECRET", raising=False)
    with pytest.raises(ValueError):
        notifier_from_environment()
    monkeypatch.setenv("WAVIA_ALERT_WEBHOOK_SECRET", "short")
    with pytest.raises(ValueError):
        notifier_from_environment()
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.setenv("WAVIA_ALERT_WEBHOOK_URL", "http://alerts.example/hook")
    monkeypatch.setenv("WAVIA_ALERT_WEBHOOK_SECRET", SECRET)
    with pytest.raises(ValueError):
        notifier_from_environment()


@pytest.mark.asyncio
async def test_raise_safely_never_propagates_storage_failure() -> None:
    class Broken(InMemoryAlertRepository):
        async def upsert_open(self, **_kwargs):  # type: ignore[override]
            raise ConnectionError("db down")

    service = AlertService(Broken())
    assert (
        await service.raise_safely(
            alert_key="x:y",
            code=AlertCode.JOB_RUN_FAILED,
            severity=AlertSeverity.ERROR,
            summary="s",
        )
        is None
    )


@pytest.mark.asyncio
async def test_exhausted_provider_chain_raises_critical_alert() -> None:
    from core.providers.exceptions import NoProviderAvailableError
    from core.providers.failover import FailoverRouter

    service = _service()
    set_process_alert_service(service)
    try:
        router = FailoverRouter(priority=["primary", "secondary"])

        async def always_fail(route: str) -> str:
            raise RuntimeError("down")

        with pytest.raises(NoProviderAvailableError):
            await router.call_with_failover("tts", "en", always_fail)
    finally:
        set_process_alert_service(None)
    alerts = await service.repository.list_alerts(status="open")
    assert [a.code for a in alerts] == [AlertCode.PROVIDER_CHAIN_EXHAUSTED]
    assert alerts[0].severity is AlertSeverity.CRITICAL
    assert alerts[0].facts == {"category": "tts", "failed_routes": 2}


def test_prometheus_rules_reference_only_exported_metrics() -> None:
    rules = yaml.safe_load(
        (REPO / "infra/observability/prometheus-alerts.yml").read_text(encoding="utf-8")
    )
    exported = set(get_metrics_registry().names())
    builtin = {"up"}
    referenced: set[str] = set()
    for group in rules["groups"]:
        for rule in group["rules"]:
            assert rule["alert"].startswith("Wavia")
            assert rule["labels"]["severity"]
            for name in re.findall(r"\b(ucve_[a-z_]+)", rule["expr"]):
                referenced.add(re.sub(r"_(bucket|count|sum)$", "", name))
            referenced |= builtin & set(re.findall(r"\b([a-z_]+)\{", rule["expr"]))
    missing = {m for m in referenced if m not in exported and m not in builtin}
    assert not missing, missing
    assert "ucve_turn_latency_ms" in referenced


def test_mint_soft_cap_raises_tenant_alert_visible_only_to_that_tenant() -> None:
    """The tenant route lists only its own alerts; other tenants get 403."""
    import asyncio

    from fastapi.testclient import TestClient

    from control_plane.app import app
    from control_plane.routes.session import MintContext, _raise_quota_alert

    tenant = str(uuid4())
    with TestClient(app) as client:
        service = app.state.alert_service
        ctx = MintContext(alerts=service)
        asyncio.run(_raise_quota_alert(ctx, tenant, exhausted=False))
        asyncio.run(_raise_quota_alert(ctx, tenant, exhausted=False))
        alerts = asyncio.run(service.repository.list_tenant_alerts(uuid4()))
        assert alerts == []
        mine = asyncio.run(
            service.repository.list_tenant_alerts(__import__("uuid").UUID(tenant))
        )
        assert len(mine) == 1 and mine[0].occurrences == 2
        assert client.get(f"/v1/alerts/{tenant}").status_code == 401
