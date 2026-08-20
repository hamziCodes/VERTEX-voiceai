"""UCVE Real-Time In-Session Usage Collector."""

from __future__ import annotations

from typing import Any

from core.metering.kinds import AGENT_SEC, LLM_TOKENS, STT_SEC, TTS_SEC


class UsageCollector:
    """Collects per-session real-time usage metrics during active call."""

    def __init__(self, tenant_id: str, session_id: str) -> None:
        self.tenant_id = tenant_id
        self.session_id = session_id
        self._totals: dict[str, float] = {
            STT_SEC: 0.0,
            TTS_SEC: 0.0,
            LLM_TOKENS: 0.0,
            AGENT_SEC: 0.0,
        }

    def add_stt_duration(self, seconds: float) -> None:
        if seconds > 0:
            self._totals[STT_SEC] += seconds

    def add_tts_duration(self, seconds: float) -> None:
        if seconds > 0:
            self._totals[TTS_SEC] += seconds

    def add_llm_tokens(self, tokens: int) -> None:
        if tokens > 0:
            self._totals[LLM_TOKENS] += float(tokens)

    def add_agent_duration(self, seconds: float) -> None:
        if seconds > 0:
            self._totals[AGENT_SEC] += seconds

    def flush_session_totals(self) -> dict[str, float]:
        """Return aggregated usage metrics for session flush."""
        return dict(self._totals)
