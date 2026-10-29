"""Telephony Failover Router — Secondary trunk failover arbitration."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from telephony_gateway.trunk_config import SIPTrunkConfig, SIPTrunkRole

logger = logging.getLogger(__name__)


class TrunkUnavailableError(Exception):
    """Raised when primary trunk is down and no secondary trunk is configured."""

    pass


class TelephonyFailoverRouter:
    """Routes call sessions to healthy trunks in configured priority order."""

    def __init__(self, trunks: Sequence[SIPTrunkConfig]) -> None:
        if not trunks:
            raise ValueError(
                "TelephonyFailoverRouter requires at least 1 SIPTrunkConfig"
            )
        # Sort by priority ascending (1 = highest)
        self.trunks: list[SIPTrunkConfig] = sorted(trunks, key=lambda t: t.priority)

    @classmethod
    async def from_db(cls, db_pool: Any, tenant_id: Any) -> TelephonyFailoverRouter:
        """Load tenant SIP trunks from PostgreSQL under tenant RLS."""
        from telephony_gateway.trunk_config import (
            SIPTrunkConfig,
            SIPTrunkProvider,
        )

        async with db_pool.acquire() as conn:
            await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))
            rows = await conn.fetch(
                """
                SELECT id, provider, priority, enabled, credentials_ref, connection_id
                FROM sip_trunks
                WHERE tenant_id = $1 AND enabled = true
                ORDER BY priority ASC
                """,
                tenant_id,
            )
            trunks = [
                SIPTrunkConfig(
                    trunk_id=r["id"],
                    provider=SIPTrunkProvider(r["provider"]),
                    credentials_ref=r["credentials_ref"],
                    connection_id=r["connection_id"],
                    priority=r["priority"],
                    role=SIPTrunkRole.PRIMARY
                    if r["priority"] == 1
                    else SIPTrunkRole.SECONDARY,
                    enabled=r["enabled"],
                )
                for r in rows
            ]
            if not trunks:
                raise TrunkUnavailableError(
                    "No enabled telephony trunk is configured for this tenant."
                )
            return cls(trunks)

    def get_active_trunk(
        self,
        health_status_map: dict[str, bool] | None = None,
        *,
        for_new_call: bool = True,
    ) -> SIPTrunkConfig:
        """Return the highest priority healthy trunk.

        If health_status_map is provided:
          - 'true' = healthy, 'false' = down.
          - If primary fails and secondary exists & healthy, routes to secondary.
          - If no configured trunk is healthy, raise TrunkUnavailableError.
        """
        if not for_new_call:
            raise TrunkUnavailableError(
                "Carrier failover is not supported for established calls."
            )

        health_status = health_status_map or {}
        saw_unknown = False
        saw_unimplemented = False
        saw_not_ready = False

        for trunk in self.trunks:
            if not trunk.enabled:
                continue

            if trunk.provider.value != "telnyx":
                saw_unimplemented = True
                continue
            if not trunk.validate():
                saw_not_ready = True
                continue

            ref_id = str(trunk.trunk_id)
            if ref_id in health_status:
                is_healthy = health_status[ref_id]
            elif trunk.provider.value in health_status:
                is_healthy = health_status[trunk.provider.value]
            else:
                saw_unknown = True
                continue

            if is_healthy:
                return trunk

        if saw_unknown:
            raise TrunkUnavailableError("Telephony trunk readiness is unknown.")
        if saw_not_ready:
            raise TrunkUnavailableError(
                "The configured Telnyx trunk is not ready for outbound calls."
            )
        if saw_unimplemented:
            raise TrunkUnavailableError(
                "The configured telephony provider is not implemented for "
                "outbound calls."
            )

        # If primary failed and no healthy trunk found
        primary = self.trunks[0]
        raise TrunkUnavailableError(
            f"Primary trunk '{primary.provider.value}' is down and no healthy "
            "secondary trunk is available."
        )
