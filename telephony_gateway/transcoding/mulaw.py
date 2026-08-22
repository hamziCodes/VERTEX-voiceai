"""G.711 μ-law ↔ PCM16 Transcoder with G.711 Lookup Table for Python 3.12+ Compatibility."""

from __future__ import annotations

import struct

# Pre-computed G.711 μ-law to 16-bit Signed Linear PCM Lookup Table (256 values)
_MULAW_TO_PCM16_TABLE: list[int] = []

for _i in range(256):
    _u_val = ~_i & 0xFF
    _t = ((_u_val & 0x0F) << 3) + 0x84
    _t <<= (_u_val & 0x70) >> 4
    _sample = (_t - 0x84) if (_u_val & 0x80) else (0x84 - _t)
    _MULAW_TO_PCM16_TABLE.append(max(-32768, min(32767, _sample)))


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """Decode G.711 μ-law 8-bit audio bytes to 16-bit signed PCM (8 kHz -> 8 kHz).

    Each 8-bit μ-law byte converts to 2 bytes of PCM16 (little-endian int16).
    160 bytes μ-law -> 320 bytes PCM16.
    """
    samples = [_MULAW_TO_PCM16_TABLE[b] for b in mulaw_bytes]
    return struct.pack(f"<{len(samples)}h", *samples)


def pcm16_to_mulaw(pcm_bytes: bytes) -> bytes:
    """Encode 16-bit signed PCM bytes to G.711 μ-law 8-bit audio bytes.

    Each 2 bytes of PCM16 (little-endian int16) converts to 1 byte of μ-law.
    320 bytes PCM16 -> 160 bytes μ-law.
    """
    sample_count = len(pcm_bytes) // 2
    if sample_count == 0:
        return b""

    samples = struct.unpack(f"<{sample_count}h", pcm_bytes)
    out = bytearray(sample_count)

    BIAS = 0x84
    CLIP = 32635

    for idx, pcm_val in enumerate(samples):
        sign = 0x80 if pcm_val < 0 else 0x00
        sample = abs(pcm_val)
        if sample > CLIP:
            sample = CLIP
        sample += BIAS

        exponent = 7
        mask = 0x4000
        for exp in range(7, -1, -1):
            if sample & mask:
                exponent = exp
                break
            mask >>= 1

        mantissa = (sample >> (exponent + 3)) & 0x0F
        u_val = sign | (exponent << 4) | mantissa
        out[idx] = (~u_val) & 0xFF

    return bytes(out)


def resample_pcm16_8k_to_16k(pcm8k_bytes: bytes) -> bytes:
    """Resample 8 kHz PCM16 mono audio to 16 kHz PCM16 mono audio (2x interpolation).

    320 bytes (160 samples @ 8kHz) -> 640 bytes (320 samples @ 16kHz).
    """
    sample_count = len(pcm8k_bytes) // 2
    if sample_count == 0:
        return b""

    samples = struct.unpack(f"<{sample_count}h", pcm8k_bytes)
    out_samples = []

    for i in range(sample_count - 1):
        s0 = samples[i]
        s1 = samples[i + 1]
        out_samples.append(s0)
        out_samples.append((s0 + s1) // 2)

    if sample_count > 0:
        out_samples.append(samples[-1])
        out_samples.append(samples[-1])

    return struct.pack(f"<{len(out_samples)}h", *out_samples)


def resample_pcm16_16k_to_8k(pcm16k_bytes: bytes) -> bytes:
    """Downsample 16 kHz PCM16 mono audio to 8 kHz PCM16 mono audio (2:1 decimation).

    640 bytes (320 samples @ 16kHz) -> 320 bytes (160 samples @ 8kHz).
    """
    sample_count = len(pcm16k_bytes) // 2
    if sample_count == 0:
        return b""

    samples = struct.unpack(f"<{sample_count}h", pcm16k_bytes)
    out_samples = samples[::2]
    return struct.pack(f"<{len(out_samples)}h", *out_samples)
