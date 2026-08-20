"""UCVE Right-to-Left (RTL) Voice Validation Gate."""

from __future__ import annotations


class RTLVoiceValidator:
    """Validates TTS voice IDs for RTL languages (Arabic, Urdu) prior to agent publish."""

    _validated_rtl_voices: set[str] = {
        "ar-multilingual-1",
        "ur-standard-1",
        "cartesia-ar-v1",
        "cartesia-ur-v1",
    }

    @classmethod
    def validate_voice_for_publish(cls, language_code: str, tts_voice_id: str) -> bool:
        """Return True if voice ID is validated for RTL language publish."""
        if language_code.lower() in ("ar", "ur"):
            return tts_voice_id in cls._validated_rtl_voices
        return True  # LTR languages do not require RTL voice gate
