"""UCVE Canonical Types & Domain Contracts Package."""

from __future__ import annotations

from core.types.audio import AudioEncoding, AudioFrame
from core.types.constants import (
    BYTES_PER_SAMPLE,
    CANONICAL_CHANNELS,
    CANONICAL_SAMPLE_RATE,
    FRAME_BYTES,
    FRAME_DURATION_MS,
    FRAME_SAMPLES,
)
from core.types.events import ControlEvent, ControlEventType
from core.types.ids import CallId, SessionId, TenantId
from core.types.resampler import Resampler, SUPPORTED_RATES

__all__ = [
    "AudioEncoding",
    "AudioFrame",
    "Resampler",
    "SUPPORTED_RATES",
    "ControlEvent",
    "ControlEventType",
    "SessionId",
    "CallId",
    "TenantId",
    "CANONICAL_SAMPLE_RATE",
    "CANONICAL_CHANNELS",
    "BYTES_PER_SAMPLE",
    "FRAME_SAMPLES",
    "FRAME_BYTES",
    "FRAME_DURATION_MS",
]
