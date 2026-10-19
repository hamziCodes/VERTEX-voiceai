"""Commit assistant context only through the client-confirmed playback boundary."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

PCM16_BYTES_PER_MS = 32
_RECENT_COMMIT_LIMIT = 128


@dataclass
class _SpeechSegment:
    text: str
    pcm_bytes: int = 0


@dataclass
class _TurnPlayback:
    segments: list[_SpeechSegment] = field(default_factory=list)


@dataclass(frozen=True)
class PlayedTextCommit:
    """Idempotent result for one assistant playback boundary."""

    turn_id: str
    text: str
    played_audio_ms: float
    played_pcm_bytes: int
    generated_pcm_bytes: int
    complete: bool


class TurnCommitTracker:
    """Tracks generated PCM and converts client playback time into a word boundary."""

    def __init__(self) -> None:
        self._turns: dict[str, _TurnPlayback] = {}
        self._recent: OrderedDict[str, PlayedTextCommit] = OrderedDict()

    def begin_turn(self, turn_id: str) -> None:
        if turn_id not in self._recent:
            self._turns.setdefault(turn_id, _TurnPlayback())

    def start_segment(self, turn_id: str, text: str) -> None:
        cleaned = " ".join(text.split())
        if not cleaned:
            return
        self.begin_turn(turn_id)
        self._turns[turn_id].segments.append(_SpeechSegment(cleaned))

    def add_audio(self, turn_id: str, pcm_bytes: int) -> None:
        if pcm_bytes <= 0:
            return
        turn = self._turns.get(turn_id)
        if turn is None or not turn.segments:
            return
        turn.segments[-1].pcm_bytes += pcm_bytes - (pcm_bytes % 2)

    def generated_audio_ms(self, turn_id: str) -> float:
        turn = self._turns.get(turn_id)
        if turn is None:
            cached = self._recent.get(turn_id)
            return cached.played_audio_ms if cached and cached.complete else 0.0
        return sum(segment.pcm_bytes for segment in turn.segments) / PCM16_BYTES_PER_MS

    def commit(
        self,
        turn_id: str,
        *,
        played_audio_ms: float | None = None,
        complete: bool = False,
    ) -> PlayedTextCommit:
        cached = self._recent.get(turn_id)
        if cached is not None:
            return cached

        turn = self._turns.pop(turn_id, _TurnPlayback())
        generated_bytes = sum(segment.pcm_bytes for segment in turn.segments)
        requested_bytes = (
            generated_bytes
            if complete
            else int(max(0.0, played_audio_ms or 0.0) * PCM16_BYTES_PER_MS)
        )
        played_bytes = min(generated_bytes, requested_bytes)
        remaining = played_bytes
        committed_parts: list[str] = []

        for segment in turn.segments:
            if remaining <= 0 or segment.pcm_bytes <= 0:
                break
            if remaining >= segment.pcm_bytes:
                committed_parts.append(segment.text)
                remaining -= segment.pcm_bytes
                continue
            words = segment.text.split()
            word_count = int(len(words) * (remaining / segment.pcm_bytes))
            if word_count > 0:
                committed_parts.append(" ".join(words[:word_count]))
            break

        result = PlayedTextCommit(
            turn_id=turn_id,
            text=" ".join(committed_parts).strip(),
            played_audio_ms=played_bytes / PCM16_BYTES_PER_MS,
            played_pcm_bytes=played_bytes,
            generated_pcm_bytes=generated_bytes,
            complete=complete and played_bytes == generated_bytes,
        )
        self._recent[turn_id] = result
        self._recent.move_to_end(turn_id)
        while len(self._recent) > _RECENT_COMMIT_LIMIT:
            self._recent.popitem(last=False)
        return result

    def discard_all(self) -> None:
        self._turns.clear()

    @property
    def active_turn_ids(self) -> tuple[str, ...]:
        return tuple(self._turns)
