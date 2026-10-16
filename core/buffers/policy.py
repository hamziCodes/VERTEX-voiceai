"""UCVE Buffer Policy & Overflow Enums."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OverflowPolicy(StrEnum):
    """Overflow drop policies for bounded queues."""

    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    BLOCK = "block"


@dataclass(frozen=True)
class BufferPolicy:
    """Configuration contract for a bounded async queue."""

    name: str
    maxsize: int
    overflow: OverflowPolicy | str = OverflowPolicy.DROP_OLDEST

    def __post_init__(self) -> None:
        if isinstance(self.overflow, str):
            object.__setattr__(self, "overflow", OverflowPolicy(self.overflow))
        if self.maxsize < 0:
            raise ValueError(f"Queue maxsize cannot be negative. Got {self.maxsize}.")


# Blueprint File 02 §1.1 Standard Queue Policies
INBOUND_MIC_POLICY = BufferPolicy(
    name="inbound_mic", maxsize=100, overflow=OverflowPolicy.BLOCK
)

VAD_INTERNAL_POLICY = BufferPolicy(
    name="vad_internal", maxsize=100, overflow=OverflowPolicy.DROP_OLDEST
)

TRANSCRIPT_PARTIAL_POLICY = BufferPolicy(
    name="transcript_partial", maxsize=200, overflow=OverflowPolicy.DROP_OLDEST
)

OUTBOUND_TTS_POLICY = BufferPolicy(
    name="outbound_tts", maxsize=200, overflow=OverflowPolicy.BLOCK
)

SENTENCE_BRIDGE_POLICY = BufferPolicy(
    name="sentence_bridge", maxsize=50, overflow=OverflowPolicy.DROP_OLDEST
)

DEFAULT_POLICIES: dict[str, BufferPolicy] = {
    INBOUND_MIC_POLICY.name: INBOUND_MIC_POLICY,
    VAD_INTERNAL_POLICY.name: VAD_INTERNAL_POLICY,
    TRANSCRIPT_PARTIAL_POLICY.name: TRANSCRIPT_PARTIAL_POLICY,
    OUTBOUND_TTS_POLICY.name: OUTBOUND_TTS_POLICY,
    SENTENCE_BRIDGE_POLICY.name: SENTENCE_BRIDGE_POLICY,
}
