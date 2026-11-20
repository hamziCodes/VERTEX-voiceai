"""Free, network-independent latency baseline runner."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from core.providers.interfaces.llm import LLMConfig
from core.providers.interfaces.stt import STTConfig
from core.providers.interfaces.tts import TTSConfig
from core.types.audio import AudioFrame
from tests.latency.fakes import ScriptedLLM, ScriptedSTT, ScriptedTTS
from tests.latency.fixtures.generate import generate_case_pcm
from tests.latency.network_guard import deny_outbound_network
from tests.latency.report import LatencyReport, LatencySample

_MANIFEST = Path(__file__).parent / "fixtures" / "manifest.json"


def _now_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def _load_cases(fixture_ids: tuple[str, ...] | None) -> list[dict[str, object]]:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if fixture_ids is None:
        return cases
    wanted = set(fixture_ids)
    selected = [case for case in cases if case["id"] in wanted]
    found = {case["id"] for case in selected}
    missing = sorted(wanted - found)
    if missing:
        raise ValueError(f"unknown latency fixtures: {missing}")
    return selected


async def _run_turn(case: dict[str, object]) -> LatencySample:
    start = time.perf_counter()
    acoustic_eos_ms = _now_ms(start)
    await asyncio.sleep(0)
    vad_end_ms = _now_ms(start)

    sample_rate = int(case["sample_rate"])
    pcm = generate_case_pcm(case)

    async def audio_stream():
        yield AudioFrame(
            pcm16=pcm,
            sample_rate=sample_rate,
            sequence=1,
        )

    stt = ScriptedSTT(final_text=f"fixture {case['id']}")
    async for _ in stt.transcribe_stream(
        audio_stream(),
        STTConfig(language=str(case["language"]), sample_rate=sample_rate),
    ):
        pass
    stt_final_ms = _now_ms(start)

    await asyncio.sleep(0)
    rag_end_ms = _now_ms(start)

    llm = ScriptedLLM(chunks=("Ready ", "now."))
    llm_first_token_ms = 0.0
    first_speakable_text_ms = 0.0
    speech = ""
    async for chunk in llm.generate_stream(
        [{"role": "user", "content": f"fixture {case['id']}"}],
        LLMConfig(model="test"),
    ):
        if llm_first_token_ms == 0.0:
            llm_first_token_ms = _now_ms(start)
        speech += chunk.text
        if first_speakable_text_ms == 0.0 and any(mark in speech for mark in ".!?"):
            first_speakable_text_ms = _now_ms(start)

    tts = ScriptedTTS(chunks=(b"\x00\x00" * 160, b"\x00\x00" * 160))
    tts_first_byte_ms = 0.0
    server_send_ms = 0.0
    queue_high_water = 0
    output_chunks = 0
    async for _ in tts.synthesize_stream(
        speech, TTSConfig(voice_id="test", sample_rate=16000)
    ):
        output_chunks += 1
        queue_high_water = max(queue_high_water, output_chunks)
        if tts_first_byte_ms == 0.0:
            tts_first_byte_ms = _now_ms(start)
            server_send_ms = _now_ms(start)

    scheduled_playback_ms = _now_ms(start)
    acknowledged_playback_ms = _now_ms(start)
    return LatencySample(
        fixture_id=str(case["id"]),
        turn_id=str(uuid4()),
        provider_mode="test",
        acoustic_eos_ms=acoustic_eos_ms,
        vad_end_ms=vad_end_ms,
        stt_final_ms=stt_final_ms,
        rag_end_ms=rag_end_ms,
        llm_first_token_ms=llm_first_token_ms,
        first_speakable_text_ms=first_speakable_text_ms,
        tts_first_byte_ms=tts_first_byte_ms,
        server_send_ms=server_send_ms,
        scheduled_playback_ms=scheduled_playback_ms,
        acknowledged_playback_ms=acknowledged_playback_ms,
        queue_high_water=queue_high_water,
    )


def _commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unknown"


async def run_baseline(
    *,
    output_dir: Path,
    repetitions: int = 3,
    fixture_ids: tuple[str, ...] | None = None,
    commit: str | None = None,
) -> tuple[LatencyReport, Path]:
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    cases = _load_cases(fixture_ids)
    samples: list[LatencySample] = []
    with deny_outbound_network() as attempts:
        for case in cases:
            for _ in range(repetitions):
                samples.append(await _run_turn(case))
    if attempts:
        raise RuntimeError(f"offline baseline attempted network access: {attempts}")
    report = LatencyReport.from_samples(
        samples,
        commit=commit or _commit(),
        runtime_profile="offline-scripted",
    )
    artifact = report.write_json(output_dir)
    return report, artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/latency"))
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    report, artifact = asyncio.run(
        run_baseline(output_dir=args.output_dir, repetitions=args.repetitions)
    )
    print(report.concise_table())
    print(f"artifact: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
