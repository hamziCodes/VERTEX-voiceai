"""Helper to generate or access synthetic PCM audio fixtures for E2E tests."""

from __future__ import annotations

from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent


def get_synthetic_pcm(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate synthetic PCM16 mono silence/tone for testing without real voice files."""
    num_samples = int(sample_rate * duration_sec)
    return b"\x00\x00" * num_samples


# Pre-generate sample clips
EN_SAMPLE_PATH = AUDIO_DIR / "en_sample.pcm"
UR_SAMPLE_PATH = AUDIO_DIR / "ur_sample.pcm"

if not EN_SAMPLE_PATH.is_file():
    EN_SAMPLE_PATH.write_bytes(get_synthetic_pcm(1.0))

if not UR_SAMPLE_PATH.is_file():
    UR_SAMPLE_PATH.write_bytes(get_synthetic_pcm(1.0))
