"""Latency Demotion Rule — Opt-in provider demotion arbitration."""

from __future__ import annotations

import logging
from core.latency.slo_policy import SLOPolicy

logger = logging.getLogger(__name__)


class LatencyDemotionRule:
    """Evaluates provider latency breaches and triggers demotion if tenant opt-in enabled."""

    def __init__(self, slow_turns_threshold: int = 5) -> None:
        self.slow_turns_threshold = slow_turns_threshold
        self._provider_slow_counts: dict[str, int] = {}

    def record_turn_latency(
        self,
        provider_name: str,
        latency_ms: float,
        budget_ms: float,
        slo_policy: SLOPolicy,
    ) -> bool:
        """Record turn latency and evaluate demotion rule.

        Returns True if demotion was triggered; False otherwise.
        """
        if latency_ms > budget_ms:
            count = self._provider_slow_counts.get(provider_name, 0) + 1
            self._provider_slow_counts[provider_name] = count
            logger.warning(
                "Provider '%s' turn latency (%.1f ms) exceeded budget (%.1f ms) [slow count: %d/%d]",
                provider_name,
                latency_ms,
                budget_ms,
                count,
                self.slow_turns_threshold,
            )

            if count >= self.slow_turns_threshold:
                if slo_policy.enforce_demotion:
                    logger.error("Opt-in demotion triggered for provider '%s'", provider_name)
                    return True
                else:
                    logger.warning("Warn-only mode: Demotion skipped for provider '%s' (enforce_demotion=false)", provider_name)
                    return False
        else:
            self._provider_slow_counts[provider_name] = 0

        return False
