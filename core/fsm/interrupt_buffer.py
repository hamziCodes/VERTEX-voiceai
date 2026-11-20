"""UCVE Interrupt Buffer for Post-Barge Utterance Retention."""

from __future__ import annotations


class InterruptBuffer:
    """Holds partial and final transcripts received during barge-in arbitration."""

    def __init__(self) -> None:
        self._partials: list[str] = []
        self._finals: list[str] = []

    def append_partial(self, text: str) -> None:
        """Append interim partial STT hypothesis."""
        cleaned = " ".join(text.split())
        if cleaned and (not self._partials or self._partials[-1] != cleaned):
            self._partials.append(cleaned)

    def append_final(self, text: str) -> None:
        """Append finalized STT hypothesis."""
        cleaned = " ".join(text.split())
        if cleaned and (not self._finals or self._finals[-1] != cleaned):
            self._finals.append(cleaned)

    def get_next_turn_input(self) -> str:
        """Extract the retained interruption once, then reset the buffer."""
        if self._finals:
            words: list[str] = []
            for fragment in self._finals:
                incoming = fragment.split()
                overlap = 0
                for size in range(min(len(words), len(incoming)), 0, -1):
                    if words[-size:] == incoming[:size]:
                        overlap = size
                        break
                words.extend(incoming[overlap:])
            result = " ".join(words)
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
