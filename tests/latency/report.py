"""Versioned latency samples and aggregate reports for offline baselines."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import median


@dataclass(frozen=True, slots=True)
class LatencySample:
    fixture_id: str
    turn_id: str
    provider_mode: str
    acoustic_eos_ms: float
    vad_end_ms: float = 0.0
    stt_final_ms: float = 0.0
    rag_end_ms: float = 0.0
    llm_first_token_ms: float = 0.0
    first_speakable_text_ms: float = 0.0
    tts_first_byte_ms: float = 0.0
    server_send_ms: float = 0.0
    scheduled_playback_ms: float = 0.0
    acknowledged_playback_ms: float = 0.0
    dropped_input_frames: int = 0
    dropped_output_chunks: int = 0
    queue_high_water: int = 0
    sample_drift_ms: float = 0.0
    interruption_to_silence_ms: float | None = None
    excluded_reason: str | None = None

    @property
    def e2e_ms(self) -> float | None:
        if self.excluded_reason or self.acknowledged_playback_ms <= 0:
            return None
        return max(0.0, self.acknowledged_playback_ms - self.acoustic_eos_ms)

    def stage_durations_ms(self) -> dict[str, float]:
        points = (
            ("vad_tail", self.acoustic_eos_ms, self.vad_end_ms),
            ("stt_after_vad", self.vad_end_ms, self.stt_final_ms),
            ("rag", self.stt_final_ms, self.rag_end_ms),
            ("llm_ttft", self.rag_end_ms, self.llm_first_token_ms),
            (
                "speakable_after_token",
                self.llm_first_token_ms,
                self.first_speakable_text_ms,
            ),
            ("tts_ttfb", self.first_speakable_text_ms, self.tts_first_byte_ms),
            ("server_send", self.tts_first_byte_ms, self.server_send_ms),
            ("client_schedule", self.server_send_ms, self.scheduled_playback_ms),
            (
                "playback_ack",
                self.scheduled_playback_ms,
                self.acknowledged_playback_ms,
            ),
        )
        return {
            name: max(0.0, end - start)
            for name, start, end in points
            if end > 0 and end >= start
        }


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


@dataclass(frozen=True, slots=True)
class LatencyReport:
    schema_version: int
    generated_at: str
    commit: str
    runtime_profile: str
    sample_count: int
    excluded_count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    stage_medians_ms: dict[str, float]
    samples: tuple[LatencySample, ...] = field(repr=False)

    @classmethod
    def from_samples(
        cls,
        samples: list[LatencySample],
        *,
        commit: str,
        runtime_profile: str,
    ) -> LatencyReport:
        included = [sample for sample in samples if sample.e2e_ms is not None]
        e2e = [sample.e2e_ms for sample in included]
        stage_names = {
            name for sample in included for name in sample.stage_durations_ms()
        }
        stage_medians = {
            name: median(
                sample.stage_durations_ms()[name]
                for sample in included
                if name in sample.stage_durations_ms()
            )
            for name in sorted(stage_names)
        }
        return cls(
            schema_version=1,
            generated_at=datetime.now(UTC).isoformat(),
            commit=commit,
            runtime_profile=runtime_profile,
            sample_count=len(included),
            excluded_count=len(samples) - len(included),
            p50_ms=_nearest_rank(e2e, 0.50),
            p95_ms=_nearest_rank(e2e, 0.95),
            p99_ms=_nearest_rank(e2e, 0.99),
            stage_medians_ms=stage_medians,
            samples=tuple(samples),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def write_json(self, output_dir: Path, *, timestamp: str | None = None) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        base = output_dir / f"latency-baseline-{stamp}.json"
        candidate = base
        suffix = 2
        while candidate.exists():
            candidate = output_dir / f"latency-baseline-{stamp}-{suffix:02d}.json"
            suffix += 1
        with candidate.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(self.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        return candidate

    def concise_table(self) -> str:
        return (
            "samples  excluded  p50_ms  p95_ms  p99_ms\n"
            f"{self.sample_count:7d}  {self.excluded_count:8d}  "
            f"{self.p50_ms:6.1f}  {self.p95_ms:6.1f}  {self.p99_ms:6.1f}"
        )
