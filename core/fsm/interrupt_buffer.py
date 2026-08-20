"""UCVE Interrupt Buffer for Post-Barge Utterance Retention."""

from __future__ import annotations


class InterruptBuffer:
    """Holds partial and final transcripts received during barge-in arbitration."""

    def __init__(self) -> None:
        self._partials: list[str] = []
        self._finals: list[str] = []

    def append_partial(self, text: str) -> None:
        """Append interim partial STT hypothesis."""
        if text and text.strip():
            self._partials.append(text.strip())

    def append_final(self, text: str) -> None:
        """Append finalized STT hypothesis."""
        if text and text.strip():
            self._finals.append(text.strip())

    def get_next_turn_input(self) -> str:
        """Extract retained interrupting utterance as next turn input and reset buffer."""
        if self._finals:
            result = " ".join(self._finals)
        elif self._partials:
            result = self._partials[-1]
        else:
            result = ""
        self.clear()
        return result

    def clear(self) -> None:
        """Clear all buffered transcripts."""
        self._partials.clear()
        self._finals.clear()

    @property
    def has_content(self) -> bool:
        """Return True if any transcript has been buffered."""
        return bool(self._finals or self._partials)
