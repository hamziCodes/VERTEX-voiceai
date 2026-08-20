"""UCVE Barge-In Verification & Interruption Configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BargeInConfig:
    """Configuration parameters governing barge-in verification and commitment."""

    verify_window_ms: int = 700
    min_sustained_speech_ms: int = 300
    text_backup_word_threshold: int = 3
    reentrancy_guard: bool = True
