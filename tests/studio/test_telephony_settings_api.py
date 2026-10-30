from __future__ import annotations

from tests.studio.test_identity_api import _create_workspace, _headers


def test_telephony_settings_report_readiness_without_carrier_action(studio_api) -> None:
    client, app = studio_api
    tenant_id, _ = _create_workspace(client)

    class _ForbiddenCarrierService:
        async def create_call(self, request):
            raise AssertionError("settings must not place a carrier call")

    app.state.outbound_call_service = _ForbiddenCarrierService()
    initial = client.get(
        "/v1/telephony/settings", headers=_headers("owner-token", tenant_id)
    )
    updated = client.put(
        "/v1/telephony/settings",
        headers=_headers("owner-token", tenant_id),
        json={
            "outbound_enabled": True,
            "allowed_destinations": ["+15551234567"],
            "calling_timezone": "Asia/Karachi",
            "window_start": "09:00",
            "window_end": "17:00",
            "max_concurrent_calls": 1,
            "max_calls_per_minute": 2,
            "daily_spend_cap_cents": 500,
            "reserved_spend_cents_per_call": 25,
            "max_call_duration_seconds": 600,
        },
    )

    assert initial.status_code == 200
    assert initial.json()["readiness"]["state"] == "not_configured"
    assert updated.status_code == 200
    assert updated.json()["policy"]["outbound_enabled"] is True
    assert updated.json()["readiness"]["state"] == "not_configured"
    assert "credential" not in updated.text.lower()
