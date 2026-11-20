"""UCVE Barge-In Verify Engine — pause, verify, then commit-or-resume.

Production interrupt behaviour: when the user speaks while the agent is
talking we *pause* egress immediately and run a short verification window
before committing the interrupt. Coughs, desk taps and short noises resume the
agent; sustained speech (or a multi-word STT partial) commits the barge-in.

Harvested pattern: ``Multilingual_AI_Voice_Agent`` ``session.py`` verification
window (``_run_verification_window``).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.listening.config import FRAME_MS, ListeningPipelineConfig

_MaybeAwaitable = Callable[[], Awaitable[None] | None]


@dataclass
class BargeVerifyDecision:
    """Outcome of a verification window."""

    committed: bool
    sustained_speech_ms: float
    partial_words: int
    reason: str


class BargeVerifyEngine:
    """Coordinates the pause → verify → commit/resume barge-in flow."""

    def __init__(
        self,
        config: ListeningPipelineConfig,
        *,
        speech_threshold: float = 0.5,
    ) -> None:
        self._verify_window_ms = config.barge_verify_window_ms
        self._min_sustained_ms = config.barge_min_sustained_speech_ms
        self._text_backup_words = config.barge_text_backup_words
        self._speech_threshold = speech_threshold
        self._verifying = False
        self._sustained_ms = 0.0
        self._partial_words = 0
        self._decision_event: asyncio.Event | None = None

    @property
    def is_verifying(self) -> bool:
        return self._verifying

    def note_vad(self, probability: float, *, frame_ms: float = FRAME_MS) -> None:
        """Accumulate sustained speech during the verify window (per frame)."""
        if not self._verifying:
            return
        if probability >= self._speech_threshold:
            self._sustained_ms += frame_ms
            if (
                self._decision_event is not None
                and self._sustained_ms >= self._min_sustained_ms
            ):
                self._decision_event.set()
        else:
            # Reset on a genuine gap so only *sustained* speech counts.
            self._sustained_ms = 0.0

    def note_partial(self, text: str) -> None:
        """Record an STT partial word count observed during verification."""
        if not self._verifying or not text:
            return
        self._partial_words = max(self._partial_words, len(text.split()))
        if (
            self._decision_event is not None
            and self._partial_words >= self._text_backup_words
        ):
            self._decision_event.set()

    async def run(
        self,
        *,
        pause: _MaybeAwaitable,
        resume: _MaybeAwaitable,
        commit: _MaybeAwaitable,
        is_speaking: Callable[[], bool] | None = None,
    ) -> BargeVerifyDecision:
        """Execute one verification window; reentrant calls are ignored."""
        if self._verifying:
            return BargeVerifyDecision(False, 0.0, 0, "reentrant_ignored")

        self._verifying = True
        self._sustained_ms = 0.0
        self._partial_words = 0
        self._decision_event = asyncio.Event()
        try:
            await _maybe_await(pause())
            try:
                await asyncio.wait_for(
                    self._decision_event.wait(),
                    timeout=self._verify_window_ms / 1000.0,
                )
            except TimeoutError:
                pass

            confirmed = (
                self._sustained_ms >= self._min_sustained_ms
                or self._partial_words >= self._text_backup_words
            )
            sustained = self._sustained_ms
            words = self._partial_words
        finally:
            self._verifying = False
            self._decision_event = None

        if confirmed:
            await _maybe_await(commit())
            return BargeVerifyDecision(
                True, sustained, words, "sustained_speech_confirmed"
            )
        await _maybe_await(resume())
        return BargeVerifyDecision(False, sustained, words, "false_alarm_resumed")


async def _maybe_await(value: Awaitable[None] | None) -> None:
    if asyncio.iscoroutine(value):
        await value
