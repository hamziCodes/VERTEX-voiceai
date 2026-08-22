"""Call Disposition Enum — Standardized call termination outcomes."""

from __future__ import annotations

from enum import Enum


class CallDisposition(str, Enum):
    """Standardized post-call outcome dispositions."""

    APPOINTMENT_BOOKED = "appointment_booked"
    NEEDS_FOLLOWUP = "needs_followup"
    ESCALATED_HUMAN = "escalated_human"
    INFORMATION_PROVIDED = "information_provided"
    UNRESOLVED = "unresolved"
    COMPLETED = "completed"
