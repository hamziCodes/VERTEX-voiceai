"""WebSocket session constants and helpers (R1/R2/R5)."""

from __future__ import annotations

# 256 KB max binary frame (DoS guard; pairs with uvicorn ws_max_size)
MAX_AUDIO_FRAME_BYTES = 256 * 1024
WS_MAX_SIZE_BYTES = MAX_AUDIO_FRAME_BYTES

PING_INTERVAL_SEC = 20.0
PONG_DEADLINE_MULTIPLIER = 2.0
