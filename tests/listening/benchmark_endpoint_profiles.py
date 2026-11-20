"""Generate an offline endpoint-candidate report from local FLEURS fixtures."""

from __future__ import annotations

import json
import wave
from datetime import UTC, datetime
from pathlib import Path

from core.listening.config import FRAME_MS
from core.listening.endpoint_profiles import (
    PauseFixture,
    benchmark_endpoint_candidates,
)
from core.types.audio import AudioFrame
from core.types.constants import FRAME_BYTES
from core.vad.silero_adapter import SileroVADAdapter

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "latency" / "fixtures" / "external" / "fleurs"
DEFAULT_OUTPUT = (
    ROOT
    / "Codex Fix"
    / "evidence"
    / "phase-02"
    / "endpoint-candidate-benchmark.json"
)

SYNTHETIC_PAUSE_FIXTURES = (
    PauseFixture("short-en", "en", (180, 420)),
    PauseFixture("short-ur", "ur", (240, 610)),
    PauseFixture("mixed-ur-en", "ur-en", (300, 720)),
    PauseFixture("natural-pauses", "multilingual", (350, 580, 880)),
)


def _internal_silence_runs(
    probabilities: list[float],
    threshold: float,
) -> tuple[int, ...]:
    speech = [index for index, value in enumerate(probabilities) if value >= threshold]
    if len(speech) < 2:
        return ()
    runs: list[int] = []
    current = 0
    for value in probabilities[speech[0] : speech[-1] + 1]:
        if value < threshold:
            current += 1
        elif current:
            runs.append(round(current * FRAME_MS))
            current = 0
    return tuple(runs)


def _measure_fixture(path: Path, language: str) -> PauseFixture:
    with wave.open(str(path), "rb") as wav:
        if (
            wav.getframerate() != 16000
            or wav.getnchannels() != 1
            or wav.getsampwidth() != 2
        ):
            raise ValueError(f"fixture is not 16 kHz mono PCM16: {path}")
        pcm = wav.readframes(wav.getnframes())

    vad = SileroVADAdapter()
    probabilities: list[float] = []
    for offset in range(0, len(pcm) - FRAME_BYTES + 1, FRAME_BYTES):
        frame = AudioFrame(
            pcm16=pcm[offset : offset + FRAME_BYTES],
            sample_rate=16000,
            channel_count=1,
        )
        probabilities.append(vad.process_frame(frame).probability)
    return PauseFixture(
        fixture_id=path.relative_to(FIXTURE_ROOT).as_posix(),
        language=language,
        within_utterance_pauses_ms=_internal_silence_runs(
            probabilities,
            vad.config.threshold,
        ),
    )


def generate(output: Path = DEFAULT_OUTPUT) -> Path:
    manifest_path = FIXTURE_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixtures = tuple(
        _measure_fixture(
            FIXTURE_ROOT / str(item["path"]),
            str(item["config"]),
        )
        for item in manifest["files"]
    )
    fleurs_results = benchmark_endpoint_candidates(fixtures)
    synthetic_results = benchmark_endpoint_candidates(SYNTHETIC_PAUSE_FIXTURES)

    def serialize_candidates(results):
        return [
            {
                "endpoint_ms": result.endpoint_ms,
                "pause_count": result.pause_count,
                "false_endpoint_count": result.false_endpoint_count,
                "false_endpoint_rate": result.false_endpoint_rate,
                "added_latency_ms": result.added_latency_ms,
            }
            for result in results
        ]

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "offline_local_silero",
        "dataset": manifest["dataset"],
        "dataset_revision": manifest["revision"],
        "fixture_count": len(fixtures),
        "fixtures": [
            {
                "fixture_id": fixture.fixture_id,
                "language": fixture.language,
                "internal_silence_runs_ms": fixture.within_utterance_pauses_ms,
            }
            for fixture in fixtures
        ],
        "fleurs_candidates": serialize_candidates(fleurs_results),
        "synthetic_pause_scenarios": [
            {
                "fixture_id": fixture.fixture_id,
                "language": fixture.language,
                "within_utterance_pauses_ms": fixture.within_utterance_pauses_ms,
            }
            for fixture in SYNTHETIC_PAUSE_FIXTURES
        ],
        "synthetic_candidates": serialize_candidates(synthetic_results),
        "limitations": [
            "Read-speech fixtures do not represent conversational turn-taking.",
            (
                "Metrics cover local Silero gaps, not provider finalization "
                "or network time."
            ),
            "A release default still requires the H04 listening decision.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    print(generate())
