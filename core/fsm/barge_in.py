"""UCVE Barge-In Controller, Verification Engine, & Arbitration Rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.fsm.barge_in_config import BargeInConfig
from core.fsm.cancel_contract import ThreePointCancel
from core.fsm.events import SessionEvent
from core.fsm.interrupt_buffer import InterruptBuffer

if TYPE_CHECKING:
    from core.fsm.session_fsm import SessionFSM


@dataclass(frozen=True)
class BargeInResult:
    """Outcome of barge-in verification and arbitration."""

    committed: bool
    cancelled_tasks: bool
    flushed_outbound: bool
    reason: str


class BargeInController:
    """Coordinating engine for verify-then-commit interruption arbitration."""

    def __init__(
        self,
        config: BargeInConfig | None = None,
        fsm: SessionFSM | None = None,
        cancel_contract: ThreePointCancel | None = None,
    ) -> None:
        self.config = config or BargeInConfig()
        self.fsm = fsm
        self.cancel_contract = cancel_contract or ThreePointCancel()
        self.interrupt_buffer = InterruptBuffer()
        self._barge_in_active: bool = False
        self.committed_count: int = 0
        self.false_alarm_count: int = 0

    def buffer_final(self, text: str) -> None:
        """Buffer finalized STT hypothesis during turn/barge."""
        self.interrupt_buffer.append_final(text)

    def buffer_partial(self, text: str) -> None:
        """Buffer partial STT hypothesis during turn/barge."""
        self.interrupt_buffer.append_partial(text)

    def next_turn_input(self) -> str:
        """Retrieve retained interrupting utterance for next turn."""
        return self.interrupt_buffer.get_next_turn_input()

    async def simulate_verify(
        self, sustained_speech_ms: int, within_window_ms: int
    ) -> BargeInResult:
        """Simulate verification window check and execute commit/resume decision."""
        if (
            sustained_speech_ms >= self.config.min_sustained_speech_ms
            and within_window_ms <= self.config.verify_window_ms
        ):
            return self._commit_barge_in(reason="Sustained speech threshold met.")
        else:
            return self._false_alarm(reason="Speech duration below threshold.")

    def _commit_barge_in(self, reason: str) -> BargeInResult:
        """Execute atomic commit across tasks, queues, and FSM."""
        self.committed_count += 1
        cancelled_count = self.cancel_contract.execute_cancel_and_flush()

        if self.fsm:
            if self.fsm.can_transition(SessionEvent.BARGE_CONFIRMED):
                self.fsm.trigger(SessionEvent.BARGE_CONFIRMED)

        return BargeInResult(
            committed=True,
            cancelled_tasks=True,
            flushed_outbound=True,
            reason=f"{reason} (cancelled {cancelled_count} tasks)",
        )

    def _false_alarm(self, reason: str) -> BargeInResult:
        """Handle false alarm recovery."""
        self.false_alarm_count += 1
        if self.fsm:
            if self.fsm.can_transition(SessionEvent.BARGE_FALSE_ALARM):
                self.fsm.trigger(SessionEvent.BARGE_FALSE_ALARM)

        return BargeInResult(
            committed=False,
            cancelled_tasks=False,
            flushed_outbound=False,
            reason=reason,
        )
