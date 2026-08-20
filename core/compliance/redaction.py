"""UCVE Redaction Service for Transcripts & Extraction Payloads."""

from __future__ import annotations

import copy
from typing import Any

from core.compliance.redaction_policy import RedactionPolicy
from core.observability.logging import redact_phi


class RedactionService:
    """Service applying compliance redaction rules to conversation turn transcripts."""

    def redact_transcript(
        self, turns: list[dict[str, Any]], policy: RedactionPolicy
    ) -> list[dict[str, Any]]:
        """Redact PII/PHI patterns from transcript turns according to policy."""
        if not policy.redact_pii_in_transcript:
            return turns

        redacted_turns = []
        for turn in turns:
            turn_copy = copy.deepcopy(turn)
            text = turn_copy.get("text", "")
            if isinstance(text, str):
                turn_copy["text"] = redact_phi(text)
            redacted_turns.append(turn_copy)

        return redacted_turns
