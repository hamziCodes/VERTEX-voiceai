from __future__ import annotations

import math

import numpy as np
import pytest

from core.transport.resample_egress import StreamingEgressResampler


def _tone(rate: int, duration_s: float = 0.25, frequency: float = 997.0) -> bytes:
    count = round(rate * duration_s)
    time = np.arange(count, dtype=np.float64) / rate
    samples = np.round(np.sin(2 * math.pi * frequency * time) * 20_000).astype(np.int16)
    return samples.tobytes()


@pytest.mark.parametrize("source_rate", [8000, 16000, 22050, 24000, 44100, 48000])
def test_streaming_resampler_preserves_duration_across_odd_chunk_boundaries(
    source_rate: int,
) -> None:
    pcm = _tone(source_rate)
    resampler = StreamingEgressResampler(source_rate, 16000)
    output = bytearray()
    offsets = (1, 7, 32, 111, 509, 1024)
    cursor = 0
    index = 0
    while cursor < len(pcm):
        width = offsets[index % len(offsets)]
        output.extend(resampler.process(pcm[cursor : cursor + width]))
        cursor += width
        index += 1
    output.extend(resampler.flush())

    expected_samples = round((len(pcm) // 2) * 16000 / source_rate)
    assert len(output) % 2 == 0
    assert abs((len(output) // 2) - expected_samples) <= 1


def test_streaming_resampler_matches_single_chunk_without_boundary_clicks() -> None:
    pcm = _tone(24000, duration_s=0.4)
    whole = StreamingEgressResampler(24000, 16000)
    expected = whole.process(pcm) + whole.flush()
    streamed = StreamingEgressResampler(24000, 16000)
    actual = bytearray()
    for start in range(0, len(pcm), 317):
        actual.extend(streamed.process(pcm[start : start + 317]))
    actual.extend(streamed.flush())

    np.testing.assert_array_equal(
        np.frombuffer(actual, dtype=np.int16), np.frombuffer(expected, dtype=np.int16)
    )


def test_downsampling_rejects_out_of_band_alias_energy() -> None:
    pcm = _tone(48000, duration_s=0.5, frequency=12000.0)
    resampler = StreamingEgressResampler(48000, 16000)
    output = resampler.process(pcm) + resampler.flush()
    samples = np.frombuffer(output, dtype=np.int16).astype(np.float64)
    rms = float(np.sqrt(np.mean(samples * samples)))
    assert rms < 2_000
