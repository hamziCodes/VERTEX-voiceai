"""UCVE Session State Enumeration."""

from __future__ import annotations

from enum import Enum


class SessionState(str, Enum):
    """Authoritative session states for the UCVE turn state machine."""

    CONNECTING = "CONNECTING"
    LISTENING = "LISTENING"
    USER_SPEAKING = "USER_SPEAKING"
    PROCESSING_INFERENCE = "PROCESSING_INFERENCE"
    TOOL_EXECUTING = "TOOL_EXECUTING"
    AGENT_SPEAKING = "AGENT_SPEAKING"
    BARGE_IN_VERIFY = "BARGE_IN_VERIFY"
    BARGE_IN_INTERRUPTED = "BARGE_IN_INTERRUPTED"
    DISCONNECTED = "DISCONNECTED"
