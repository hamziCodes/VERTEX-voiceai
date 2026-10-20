"""Official UCVE Python Voice Client SDK."""

from __future__ import annotations

from .client import UCVEVoiceClient
from .events import (
    AudioStartPayload,
    LatencyMetricPayload,
    PlaybackStartedPayload,
)
from .protocol_generated import (
    PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_RANGE,
    RealtimeEvent,
    RealtimeEventType,
)
from .version import SDK_VERSION_MANIFEST, __version__

__all__ = [
    "AudioStartPayload",
    "LatencyMetricPayload",
    "PlaybackStartedPayload",
    "PROTOCOL_VERSION",
    "RealtimeEvent",
    "RealtimeEventType",
    "SUPPORTED_PROTOCOL_RANGE",
    "UCVEVoiceClient",
    "SDK_VERSION_MANIFEST",
    "__version__",
]
