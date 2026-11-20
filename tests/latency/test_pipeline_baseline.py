from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.buffers.cancellation import AsyncioCancellationToken
from core.providers.interfaces.llm import LLMConfig
from core.providers.interfaces.stt import STTConfig
from core.providers.interfaces.tts import TTSConfig
from core.types.audio import AudioFrame
from tests.latency.baseline import run_baseline
from tests.latency.fakes import ScriptedLLM, ScriptedSTT, ScriptedTTS
from tests.latency.fixtures.generate import generate_case_pcm
from tests.latency.report import LatencyReport, LatencySample


def test_latency_report_uses_user_perceived_endpoint_and_nearest_rank_percentiles() -> (
    None
):
    samples = [
        LatencySample(
            fixture_id=f"case-{index}",
            turn_id=f"turn-{index}",
            provider_mode="test",
            acoustic_eos_ms=100.0,
            vad_end_ms=120.0,
            stt_final_ms=140.0,
            rag_end_ms=145.0,
            llm_first_token_ms=150.0,
            first_speakable_text_ms=160.0,
            tts_first_byte_ms=170.0,
            server_send_ms=180.0,
            scheduled_playback_ms=100.0 + latency,
            acknowledged_playback_ms=100.0 + latency,
        )
        for index, latency in enumerate((100.0, 200.0, 300.0, 400.0, 500.0), start=1)
    ]

    report = LatencyReport.from_samples(
        samples, commit="abc123", runtime_profile="test"
    )

    assert report.sample_count == 5
    assert report.excluded_count == 0
    assert report.p50_ms == 300.0
    assert report.p95_ms == 500.0
    assert report.p99_ms == 500.0
    assert report.stage_medians_ms["vad_tail"] == 20.0
    assert report.stage_medians_ms["stt_after_vad"] == 20.0


def test_latency_report_excludes_samples_with_a_reason_and_never_overwrites(
    tmp_path: Path,
) -> None:
    included = LatencySample(
        fixture_id="included",
        turn_id="turn-1",
        provider_mode="test",
        acoustic_eos_ms=0.0,
        vad_end_ms=10.0,
        stt_final_ms=20.0,
        rag_end_ms=20.0,
        llm_first_token_ms=30.0,
        first_speakable_text_ms=40.0,
        tts_first_byte_ms=50.0,
        server_send_ms=60.0,
        scheduled_playback_ms=70.0,
        acknowledged_playback_ms=80.0,
    )
    excluded = LatencySample(
        fixture_id="excluded",
        turn_id="turn-2",
        provider_mode="test",
        acoustic_eos_ms=0.0,
        excluded_reason="cancelled before playback",
    )
    report = LatencyReport.from_samples(
        [included, excluded], commit="abc123", runtime_profile="test"
    )

    first = report.write_json(tmp_path, timestamp="20261015T120000000000Z")
    second = report.write_json(tmp_path, timestamp="20261015T120000000000Z")

    assert first != second
    assert first.is_file() and second.is_file()
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["sample_count"] == 1
    assert payload["excluded_count"] == 1
    assert payload["samples"][1]["excluded_reason"] == "cancelled before playback"


@pytest.mark.asyncio
async def test_scripted_providers_stream_in_order_and_observe_cancellation() -> None:
    async def audio_stream():
        yield AudioFrame(pcm16=b"\x00\x00" * 1600, sequence=1)

    stt = ScriptedSTT(final_text="hello", first_chunk_delay_ms=0)
    transcripts = [
        item async for item in stt.transcribe_stream(audio_stream(), STTConfig())
    ]
    assert stt.provider_mode == "test"
    assert [item.text for item in transcripts] == ["hello"]

    llm = ScriptedLLM(chunks=("Hello ", "there."), first_chunk_delay_ms=0)
    chunks = [
        item
        async for item in llm.generate_stream(
            [{"role": "user", "content": "hello"}], LLMConfig(model="test")
        )
    ]
    assert [item.text for item in chunks] == ["Hello ", "there."]
    assert chunks[0].is_first_token is True

    token = AsyncioCancellationToken()
    tts = ScriptedTTS(chunks=(b"one", b"two"), first_chunk_delay_ms=0)
    stream = tts.synthesize_stream("Hello there.", TTSConfig(voice_id="test"), token)
    assert (await anext(stream)).pcm_data == b"one"
    token.cancel()
    assert [item async for item in stream] == []
    assert tts.cancellation_observed is True


def test_synthetic_corpus_covers_required_shapes() -> None:
    manifest_path = Path(__file__).parent / "fixtures" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = {case["id"] for case in payload["cases"]}

    assert {
        "short-en",
        "short-ur",
        "mixed-ur-en",
        "short-ar",
        "punctuation-free",
        "natural-pauses",
        "low-volume",
        "background-noise",
        "barge-in-early",
        "barge-in-immediate",
        "barge-in-middle",
        "barge-in-late",
        "irregular-packets",
    }.issubset(ids)
    assert {case["sample_rate"] for case in payload["cases"]}.issuperset(
        {8000, 16000, 24000, 48000}
    )
    assert all(case["representative_speech"] is False for case in payload["cases"])


def test_synthetic_fixture_generator_is_deterministic_and_matches_metadata() -> None:
    manifest_path = Path(__file__).parent / "fixtures" / "manifest.json"
    cases = json.loads(manifest_path.read_text(encoding="utf-8"))["cases"]

    for case in cases:
        first = generate_case_pcm(case)
        second = generate_case_pcm(case)
        expected_samples = int(case["sample_rate"] * case["duration_ms"] / 1000)
        assert first == second
        assert len(first) == expected_samples * 2


@pytest.mark.asyncio
async def test_baseline_runner_records_all_stages_and_test_provider_mode(
    tmp_path: Path,
) -> None:
    report, artifact = await run_baseline(
        output_dir=tmp_path,
        repetitions=2,
        fixture_ids=("short-en", "short-ur"),
        commit="abc123",
    )

    assert artifact.is_file()
    assert report.sample_count == 4
    assert report.excluded_count == 0
    assert {sample.provider_mode for sample in report.samples} == {"test"}
    assert all(
        sample.acknowledged_playback_ms >= sample.acoustic_eos_ms
        for sample in report.samples
    )
    assert all(
        sample.tts_first_byte_ms >= sample.first_speakable_text_ms
        for sample in report.samples
    )
