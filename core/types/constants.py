"""UCVE Core Audio & Transport Constants."""

from __future__ import annotations

# Canonical Audio Properties (File 02 §1.2)
CANONICAL_SAMPLE_RATE: int = 16000  # 16 kHz
CANONICAL_CHANNELS: int = 1         # Mono
BYTES_PER_SAMPLE: int = 2           # 16-bit PCM (2 bytes)

# Frame Size Constraints (Phase 01 Spec §6.3)
FRAME_SAMPLES: int = 512            # 32 ms @ 16 kHz
FRAME_BYTES: int = FRAME_SAMPLES * BYTES_PER_SAMPLE * CANONICAL_CHANNELS  # 1024 bytes
FRAME_DURATION_MS: float = (FRAME_SAMPLES / CANONICAL_SAMPLE_RATE) * 1000.0  # 32.0 ms
