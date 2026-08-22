"""Caller ID Context — E.164 caller identity details for telephony sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CallerIdContext:
    """Propagates PSTN/SIP caller identity into session orchestrator and CRM extraction."""

    from_number: str  # E.164 format, e.g. "+15550199222"
    to_number: str  # E.164 format, e.g. "+18005550199"
    sip_call_id: str = ""
    carrier: str = "telnyx"
    extra_headers: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_number": self.from_number,
            "to_number": self.to_number,
            "sip_call_id": self.sip_call_id,
            "carrier": self.carrier,
            "extra_headers": self.extra_headers,
        }
