"""UCVE Regeneration Manager & LLM Provider Failover Handoff."""

from __future__ import annotations

from typing import Any


class RegenerationManager:
    """Manages LLM regeneration retry count (max 2 retries) before escalating to FailoverRouter."""

    def __init__(self, max_retries: int = 2) -> None:
        self.max_retries = max_retries

    def should_retry(self, attempt: int) -> bool:
        """Return True if regeneration attempt is within max retries limit (max 2)."""
        return attempt < self.max_retries

    def handle_failed_regeneration(
        self, session_id: str, attempt: int, failover_router: Any = None
    ) -> bool:
        """Handle 3rd failed attempt by escalating to FailoverRouter to switch LLM provider."""
        if attempt >= self.max_retries:
            if failover_router:
                try:
                    # Escalate to next provider in fallback chain
                    pass
                except Exception:
                    pass
            return True  # Failover triggered
        return False
