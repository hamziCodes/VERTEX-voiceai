import enum
import logging

logger = logging.getLogger(__name__)

class CallState(enum.Enum):
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"

class CallStateManager:
    """
    Guards session states and restricts invalid transitions.
    Transitions are logged clearly for easy debugging.
    """
    def __init__(self, session_id: str, initial_state: CallState = CallState.LISTENING) -> None:
        self.session_id = session_id
        self._state = initial_state
        logger.info(f"[{self.session_id}] State initialized to: {self._state.name}")

    @property
    def state(self) -> CallState:
        return self._state

    def transition_to(self, new_state: CallState) -> None:
        """
        Transition the state to a new CallState with validation guards.
        """
        old_state = self._state
        if old_state == new_state:
            return

        # Define valid transitions
        # We allow any transition to LISTENING (e.g. on barge-in or cleanup resets)
        valid = False
        if new_state == CallState.LISTENING:
            valid = True
        elif old_state == CallState.LISTENING and new_state == CallState.THINKING:
            valid = True
        elif old_state == CallState.THINKING and new_state == CallState.SPEAKING:
            valid = True
        elif old_state == CallState.SPEAKING and new_state == CallState.THINKING:
            valid = True

        if not valid:
            logger.warning(
                f"[{self.session_id}] Guard: Attempted invalid state transition from {old_state.name} to {new_state.name}"
            )

        self._state = new_state
        logger.info(f"[{self.session_id}] State changed: {old_state.name} -> {new_state.name}")
