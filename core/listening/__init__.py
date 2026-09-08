"""UCVE Listening & Speaking pipeline subsystem.

Production real-time voice loop components: frame slicing, adaptive noise gate,
VAD hysteresis, pre-speech buffering, speech capture orchestration, and
pause-verify-commit barge-in. All behaviour is feature-flagged via
``ListeningPipelineConfig`` / ``SpeakingPipelineConfig`` so that the legacy
demo pipeline is preserved unless phases are explicitly enabled.
"""

from __future__ import annotations

from core.listening.barge_verify import BargeVerifyDecision, BargeVerifyEngine
from core.listening.config import (
    ListeningPipelineConfig,
    SpeakingPipelineConfig,
    ms_to_frames,
)
from core.listening.frame_slicer import FrameSlicer
from core.listening.noise_gate import AdaptiveNoiseGate
from core.listening.pre_speech_buffer import PreSpeechRingBuffer
from core.listening.speech_capture import SpeechCaptureEngine
from core.listening.vad_worker import VADWorker

__all__ = [
    "AdaptiveNoiseGate",
    "BargeVerifyDecision",
    "BargeVerifyEngine",
    "FrameSlicer",
    "ListeningPipelineConfig",
    "PreSpeechRingBuffer",
    "SpeakingPipelineConfig",
    "SpeechCaptureEngine",
    "VADWorker",
    "ms_to_frames",
]
