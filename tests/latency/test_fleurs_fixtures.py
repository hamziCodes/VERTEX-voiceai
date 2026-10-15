from __future__ import annotations

import io
import struct
import wave
from pathlib import Path

import pytest

from tests.latency.fixtures.fetch_fleurs import (
    FixtureIntegrityError,
    select_rows,
    write_verified_wav,
)


def _row(index: int, samples: int, gender: int) -> dict[str, object]:
    return {
        "row_idx": index,
        "row": {
            "id": index,
            "num_samples": samples,
            "gender": gender,
            "transcription": f"fixture {index}",
            "audio": [{"src": f"https://example.invalid/{index}.wav"}],
        },
    }


def _wav_bytes(*, sample_rate: int = 16000, samples: int = 1600) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * samples)
    return output.getvalue()


def _float_wav_bytes(*, sample_rate: int = 16000) -> bytes:
    pcm = b"".join(struct.pack("<f", value) for value in (-1.0, -0.5, 0.0, 0.5, 1.0))
    fmt = struct.pack("<HHIIHH", 3, 1, sample_rate, sample_rate * 4, 4, 32)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body


def test_select_rows_chooses_shortest_usable_male_and_female_clips() -> None:
    rows = [
        _row(1, 16000 * 9, 0),
        _row(2, 16000 * 5, 0),
        _row(3, 16000 * 4, 1),
        _row(4, 16000, 1),
        _row(5, 16000 * 3, 2),
    ]

    selected = select_rows(rows, minimum_seconds=2.0, maximum_seconds=8.0)

    assert [item["row_idx"] for item in selected] == [2, 3]


def test_select_rows_falls_back_to_two_shortest_when_preview_has_one_gender() -> None:
    rows = [
        _row(1, 16000 * 6, 1),
        _row(2, 16000 * 3, 1),
        _row(3, 16000 * 4, 1),
    ]

    selected = select_rows(rows, minimum_seconds=2.0, maximum_seconds=8.0)

    assert [item["row_idx"] for item in selected] == [2, 3]


def test_write_verified_wav_is_idempotent_and_rejects_invalid_or_changed_audio(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "clip.wav"
    content = _wav_bytes()

    metadata = write_verified_wav(destination, content)
    repeated = write_verified_wav(destination, content)

    assert metadata == repeated
    assert metadata["sample_rate"] == 16000
    assert metadata["channels"] == 1
    assert metadata["sample_width_bytes"] == 2
    assert metadata["duration_ms"] == 100.0

    with pytest.raises(FixtureIntegrityError, match="not a readable WAV"):
        write_verified_wav(tmp_path / "invalid.wav", b"not audio")
    with pytest.raises(FixtureIntegrityError, match="existing fixture differs"):
        write_verified_wav(destination, _wav_bytes(samples=3200))


def test_write_verified_wav_normalizes_float32_to_pcm16(tmp_path: Path) -> None:
    destination = tmp_path / "float-source.wav"

    metadata = write_verified_wav(destination, _float_wav_bytes())

    with wave.open(str(destination), "rb") as wav:
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1
        assert wav.getnframes() == 5
        values = struct.unpack("<5h", wav.readframes(5))
    assert values == (-32767, -16384, 0, 16384, 32767)
    assert metadata["sample_width_bytes"] == 2
