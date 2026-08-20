"""UCVE Authoritative Session State Machine (FSM)."""

from __future__ import annotations

from typing import Any

from core.fsm.errors import InvalidStateTransitionError
from core.fsm.events import SessionEvent
from core.fsm.states import SessionState
from core.fsm.turn_context import TurnContext

# Table-driven state transition matrix: (CurrentState, Event) -> NextState
TRANSITION_TABLE: dict[tuple[SessionState, SessionEvent], SessionState] = {
    # CONNECTING
    (SessionState.CONNECTING, SessionEvent.SESSION_ADMITTED): SessionState.LISTENING,
    (SessionState.CONNECTING, SessionEvent.DISCONNECT): SessionState.DISCONNECTED,
    (SessionState.CONNECTING, SessionEvent.HANGUP): SessionState.DISCONNECTED,

    # LISTENING
    (SessionState.LISTENING, SessionEvent.VAD_SPEECH_START): SessionState.USER_SPEAKING,
    (SessionState.LISTENING, SessionEvent.STT_FINAL): SessionState.PROCESSING_INFERENCE,
    (SessionState.LISTENING, SessionEvent.LLM_FIRST_TOKEN): SessionState.PROCESSING_INFERENCE,
    (SessionState.LISTENING, SessionEvent.DISCONNECT): SessionState.DISCONNECTED,
    (SessionState.LISTENING, SessionEvent.HANGUP): SessionState.DISCONNECTED,

    # USER_SPEAKING
    (SessionState.USER_SPEAKING, SessionEvent.VAD_SPEECH_END): SessionState.PROCESSING_INFERENCE,
    (SessionState.USER_SPEAKING, SessionEvent.STT_FINAL): SessionState.PROCESSING_INFERENCE,
    (SessionState.USER_SPEAKING, SessionEvent.DISCONNECT): SessionState.DISCONNECTED,
    (SessionState.USER_SPEAKING, SessionEvent.HANGUP): SessionState.DISCONNECTED,

    # PROCESSING_INFERENCE
    (SessionState.PROCESSING_INFERENCE, SessionEvent.TTS_FIRST_BYTE): SessionState.AGENT_SPEAKING,
    (SessionState.PROCESSING_INFERENCE, SessionEvent.TOOL_CALL_START): SessionState.TOOL_EXECUTING,
    (SessionState.PROCESSING_INFERENCE, SessionEvent.VAD_SPEECH_START): SessionState.USER_SPEAKING,
    (SessionState.PROCESSING_INFERENCE, SessionEvent.DISCONNECT): SessionState.DISCONNECTED,
    (SessionState.PROCESSING_INFERENCE, SessionEvent.HANGUP): SessionState.DISCONNECTED,

    # TOOL_EXECUTING
    (SessionState.TOOL_EXECUTING, SessionEvent.TOOL_RESULT): SessionState.PROCESSING_INFERENCE,
    (SessionState.TOOL_EXECUTING, SessionEvent.TTS_FIRST_BYTE): SessionState.AGENT_SPEAKING,
    (SessionState.TOOL_EXECUTING, SessionEvent.DISCONNECT): SessionState.DISCONNECTED,
    (SessionState.TOOL_EXECUTING, SessionEvent.HANGUP): SessionState.DISCONNECTED,

    # AGENT_SPEAKING
    (SessionState.AGENT_SPEAKING, SessionEvent.TTS_DRAINED): SessionState.LISTENING,
    (SessionState.AGENT_SPEAKING, SessionEvent.VAD_SPEECH_START): SessionState.BARGE_IN_VERIFY,
    (SessionState.AGENT_SPEAKING, SessionEvent.BARGE_CONFIRMED): SessionState.BARGE_IN_INTERRUPTED,
    (SessionState.AGENT_SPEAKING, SessionEvent.DISCONNECT): SessionState.DISCONNECTED,
    (SessionState.AGENT_SPEAKING, SessionEvent.HANGUP): SessionState.DISCONNECTED,

    # BARGE_IN_VERIFY
    (SessionState.BARGE_IN_VERIFY, SessionEvent.BARGE_CONFIRMED): SessionState.BARGE_IN_INTERRUPTED,
    (SessionState.BARGE_IN_VERIFY, SessionEvent.BARGE_FALSE_ALARM): SessionState.AGENT_SPEAKING,
    (SessionState.BARGE_IN_VERIFY, SessionEvent.BARGE_VERIFY_TIMEOUT): SessionState.AGENT_SPEAKING,
    (SessionState.BARGE_IN_VERIFY, SessionEvent.DISCONNECT): SessionState.DISCONNECTED,
    (SessionState.BARGE_IN_VERIFY, SessionEvent.HANGUP): SessionState.DISCONNECTED,

    # BARGE_IN_INTERRUPTED
    (SessionState.BARGE_IN_INTERRUPTED, SessionEvent.VAD_SPEECH_END): SessionState.PROCESSING_INFERENCE,
    (SessionState.BARGE_IN_INTERRUPTED, SessionEvent.STT_FINAL): SessionState.PROCESSING_INFERENCE,
    (SessionState.BARGE_IN_INTERRUPTED, SessionEvent.VAD_SPEECH_START): SessionState.USER_SPEAKING,
    (SessionState.BARGE_IN_INTERRUPTED, SessionEvent.DISCONNECT): SessionState.DISCONNECTED,
    (SessionState.BARGE_IN_INTERRUPTED, SessionEvent.HANGUP): SessionState.DISCONNECTED,
}


class SessionFSM:
    """Authoritative state machine governing a single voice AI session turn lifecycle."""

    def __init__(
        self,
        session_id: str = "default_session",
        initial_state: SessionState = SessionState.CONNECTING,
        degraded_flags: dict[str, Any] | None = None,
    ) -> None:
        self._state: SessionState = initial_state
        self.context = TurnContext(
            session_id=session_id,
            degraded_flags=degraded_flags or {},
        )

    @property
    def state(self) -> SessionState:
        """Current session state."""
        return self._state

    def _normalize_event(self, event: SessionEvent | str) -> SessionEvent:
        if isinstance(event, SessionEvent):
            return event
        try:
            return SessionEvent(event)
        except ValueError as exc:
            raise InvalidStateTransitionError(
                from_state=self._state,
                event=event,
                message=f"Unknown session event '{event}'.",
            ) from exc

    def can_transition(self, event: SessionEvent | str) -> bool:
        """Return True if event is legal from current state."""
        try:
            ev = self._normalize_event(event)
        except InvalidStateTransitionError:
            return False
        return (self._state, ev) in TRANSITION_TABLE

    def trigger(self, event: SessionEvent | str) -> SessionState:
        """Trigger state transition. Returns new state or raises InvalidStateTransitionError."""
        ev = self._normalize_event(event)
        key = (self._state, ev)
        if key not in TRANSITION_TABLE:
            raise InvalidStateTransitionError(
                from_state=self._state,
                event=ev,
                message=f"Illegal transition from state '{self._state}' via event '{ev}'.",
            )

        next_state = TRANSITION_TABLE[key]

        # Increment turn index on committed user turn completion into processing
        if (
            self._state in (SessionState.USER_SPEAKING, SessionState.BARGE_IN_INTERRUPTED)
            and next_state == SessionState.PROCESSING_INFERENCE
        ):
            self.context.turn_index += 1

        self._state = next_state
        return self._state
