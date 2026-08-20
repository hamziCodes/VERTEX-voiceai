"""UCVE Session Event Enumeration."""

from __future__ import annotations

from enum import Enum


class SessionEvent(str, Enum):
    """Authoritative session transition events."""

    SESSION_ADMITTED = "session_admitted"
    VAD_SPEECH_START = "vad_speech_start"
    VAD_SPEECH_END = "vad_speech_end"
    STT_FINAL = "stt_final"
    LLM_FIRST_TOKEN = "llm_first_token"
    TOOL_CALL_START = "tool_call_start"
    TOOL_RESULT = "tool_result"
    TTS_FIRST_BYTE = "tts_first_byte"
    TTS_DRAINED = "tts_drained"
    BARGE_VERIFY_TIMEOUT = "barge_verify_timeout"
    BARGE_CONFIRMED = "barge_confirmed"
    BARGE_FALSE_ALARM = "barge_false_alarm"
    HANGUP = "hangup"
    DISCONNECT = "disconnect"
