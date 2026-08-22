"""Telephony Failover Router — Secondary trunk failover arbitration."""

from __future__ import annotations

import logging
from typing import Sequence

from telephony_gateway.trunk_config import SIPTrunkConfig, SIPTrunkRole

logger = logging.getLogger(__name__)


class TrunkUnavailableError(Exception):
    """Raised when primary trunk is down and no secondary trunk is configured."""

    pass


class TelephonyFailoverRouter:
    """Routes call sessions to healthy trunks in configured priority order."""

    def __init__(self, trunks: Sequence[SIPTrunkConfig]) -> None:
        if not trunks:
            raise ValueError("TelephonyFailoverRouter requires at least 1 SIPTrunkConfig")
        # Sort by priority ascending (1 = highest)
        self.trunks: list[SIPTrunkConfig] = sorted(trunks, key=lambda t: t.priority)

    def get_active_trunk(self, health_status_map: dict[str, bool] | None = None) -> SIPTrunkConfig:
        """Return the highest priority healthy trunk.

        If health_status_map is provided:
          - 'true' = healthy, 'false' = down.
          - If primary fails and secondary exists & healthy, routes to secondary.
          - If primary fails and no healthy secondary exists, raises TrunkUnavailableError.
        """
        health_status = health_status_map or {}

        for trunk in self.trunks:
            if not trunk.enabled:
                continue

            ref_id = str(trunk.trunk_id)
            if ref_id in health_status:
                is_healthy = health_status[ref_id]
            elif trunk.provider.value in health_status:
                is_healthy = health_status[trunk.provider.value]
            else:
                is_healthy = True

            if is_healthy:
                return trunk

        # If primary failed and no healthy trunk found
        primary = self.trunks[0]
        raise TrunkUnavailableError(
            f"Primary trunk '{primary.provider.value}' is down and no healthy secondary trunk is available."
        )
