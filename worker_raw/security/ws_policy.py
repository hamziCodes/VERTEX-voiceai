"""WebSocket security policy for worker-raw real-time connections (Phase 32)."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any

from worker_raw.ws_constants import MAX_AUDIO_FRAME_BYTES


class WSSecurityViolation(Exception):  # noqa: N818 - public compatibility name
    """Raised when a WebSocket connection violates security policy constraints."""
    pass


_PROVIDER_OVERRIDE_KEYS = frozenset(
    {"stt_provider", "llm_provider", "llm_model", "tts_provider", "tts_voice_id"}
)


def validate_demo_provider_overrides(
    overrides: Mapping[str, str | None],
) -> dict[str, str]:
    """Allow provider query overrides only in explicitly enabled local demos."""

    selected = {
        key: str(value)
        for key, value in overrides.items()
        if key in _PROVIDER_OVERRIDE_KEYS and value not in (None, "")
    }
    if not selected:
        return {}
    environment = os.environ.get("UCVE_ENV", "development").strip().lower()
    enabled = os.environ.get("UCVE_ALLOW_DEMO_PROVIDER_OVERRIDES", "0") == "1"
    if environment not in {"development", "test"} or not enabled:
        raise WSSecurityViolation(
            "PROVIDER_OVERRIDE_FORBIDDEN: provider selection must come from the "
            "published session plan outside an explicitly enabled local demo"
        )
    return selected


class WSSecurityPolicy:
    """Enforce frame size, rate, and token rules on WebSocket connections."""

    def __init__(
        self,
        max_frame_size: int = MAX_AUDIO_FRAME_BYTES,
        max_frames_per_sec: int = 150,
        rate_limit_window_sec: float = 1.0,
    ) -> None:
        self.max_frame_size = max_frame_size
        self.max_frames_per_sec = max_frames_per_sec
        self.rate_limit_window_sec = rate_limit_window_sec
        self._connection_frame_counts: dict[str, list[float]] = {}

    def validate_frame_size(self, frame: bytes | str | int) -> bool:
        """Validate that incoming binary or text frame does not exceed max size."""
        size = frame if isinstance(frame, int) else len(frame)
        if size > self.max_frame_size:
            raise WSSecurityViolation(
                f"Frame size {size} bytes exceeds maximum allowed "
                f"{self.max_frame_size} bytes"
            )
        return True

    def check_rate_limit(self, connection_id: str) -> bool:
        """Check if incoming frame rate for connection is within allowed threshold."""
        now = time.monotonic()
        timestamps = self._connection_frame_counts.setdefault(connection_id, [])

        # Prune older than window
        cutoff = now - self.rate_limit_window_sec
        self._connection_frame_counts[connection_id] = [
            value for value in timestamps if value > cutoff
        ]

        if len(self._connection_frame_counts[connection_id]) >= self.max_frames_per_sec:
            raise WSSecurityViolation(
                f"Connection {connection_id} exceeded rate limit of "
                f"{self.max_frames_per_sec} frames/sec"
            )

        self._connection_frame_counts[connection_id].append(now)
        return True

    def validate_token_expiry(self, claims: dict[str, Any]) -> bool:
        """Verify JWT exp claim has not expired."""
        exp = claims.get("exp")
        if exp is None:
            raise WSSecurityViolation("Token missing 'exp' expiration claim")

        current_timestamp = time.time()
        if current_timestamp >= float(exp):
            raise WSSecurityViolation("Token has expired")
        return True

    def cleanup_connection(self, connection_id: str) -> None:
        """Clean up rate limiting tracking when connection terminates."""
        self._connection_frame_counts.pop(connection_id, None)
