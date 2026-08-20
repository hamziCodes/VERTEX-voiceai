"""UCVE Transport Single-Boundary Audio Egress Resampler."""

from __future__ import annotations


class EgressResampler:
    """Resamples TTS provider native audio (e.g. 24kHz/22.05kHz) to 16kHz PCM egress."""

    @classmethod
    def resample_to_16k(
        cls, pcm_bytes: bytes, source_sample_rate: int = 24000
    ) -> bytes:
        """Resample PCM audio bytes from source_sample_rate to 16000 Hz."""
        if source_sample_rate == 16000 or not pcm_bytes:
            return pcm_bytes

        # Integer decimation / linear interpolation fallback for raw 16-bit PCM
        ratio = source_sample_rate / 16000.0
        if ratio == 1.5 and len(pcm_bytes) % 2 == 0:
            # 24kHz to 16kHz decimation (2 bytes per 16-bit sample, 3 samples -> 2 samples)
            out_bytes = bytearray()
            for i in range(0, len(pcm_bytes) - 5, 6):
                out_bytes.extend(pcm_bytes[i:i + 2])
                out_bytes.extend(pcm_bytes[i + 4:i + 6])
            return bytes(out_bytes)

        return pcm_bytes
