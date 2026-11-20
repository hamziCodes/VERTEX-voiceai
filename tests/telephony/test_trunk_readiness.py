from __future__ import annotations

from uuid import uuid4

import pytest

from telephony_gateway.failover import TelephonyFailoverRouter, TrunkUnavailableError
from telephony_gateway.trunk_config import SIPTrunkConfig, SIPTrunkProvider


def _trunk(
    *,
    provider: SIPTrunkProvider = SIPTrunkProvider.TELNYX,
    credential_ref: str = "tenant-telnyx-key",
    connection_id: str = "connection-123",
    priority: int = 1,
) -> SIPTrunkConfig:
    return SIPTrunkConfig(
        trunk_id=uuid4(),
        provider=provider,
        credentials_ref=credential_ref,
        connection_id=connection_id,
        priority=priority,
    )


def test_unknown_trunk_health_is_unavailable_for_new_calls() -> None:
    router = TelephonyFailoverRouter([_trunk()])

    with pytest.raises(TrunkUnavailableError, match="readiness is unknown"):
        router.get_active_trunk({})


def test_missing_credentials_or_connection_id_is_unavailable() -> None:
    for trunk in (
        _trunk(credential_ref=""),
        _trunk(connection_id=""),
    ):
        router = TelephonyFailoverRouter([trunk])
        with pytest.raises(TrunkUnavailableError, match="not ready"):
            router.get_active_trunk({str(trunk.trunk_id): True})


def test_placeholder_provider_cannot_be_selected_even_when_marked_healthy() -> None:
    trunk = _trunk(provider=SIPTrunkProvider.TWILIO)
    router = TelephonyFailoverRouter([trunk])

    with pytest.raises(TrunkUnavailableError, match="not implemented"):
        router.get_active_trunk({str(trunk.trunk_id): True})


def test_secondary_is_selected_only_for_a_new_call() -> None:
    primary = _trunk(priority=1)
    secondary = _trunk(priority=2)
    router = TelephonyFailoverRouter([primary, secondary])
    health = {str(primary.trunk_id): False, str(secondary.trunk_id): True}

    assert router.get_active_trunk(health, for_new_call=True) == secondary
    with pytest.raises(TrunkUnavailableError, match="established calls"):
        router.get_active_trunk(health, for_new_call=False)
