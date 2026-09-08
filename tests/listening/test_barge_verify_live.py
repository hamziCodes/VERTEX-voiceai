"""Unit tests for ``core.listening.barge_verify.BargeVerifyEngine``."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from core.listening.barge_verify import BargeVerifyEngine
from core.listening.config import ListeningPipelineConfig


def _test_config() -> ListeningPipelineConfig:
    return ListeningPipelineConfig(
        enabled_phases=frozenset({"barge_verify"}),
        barge_verify_window_ms=50,
        barge_min_sustained_speech_ms=30,
        barge_text_backup_words=3,
    )


@dataclass
class BargeCallLog:
    pause: list[str] = field(default_factory=list)
    resume: list[str] = field(default_factory=list)
    commit: list[str] = field(default_factory=list)


def _make_callbacks(log: BargeCallLog) -> tuple:
    async def pause() -> None:
        log.pause.append("pause")

    async def resume() -> None:
        log.resume.append("resume")

    async def commit() -> None:
        log.commit.append("commit")

    return pause, resume, commit


@pytest.mark.asyncio
async def test_low_vad_probs_resume_without_commit() -> None:
    engine = BargeVerifyEngine(_test_config())
    log = BargeCallLog()
    pause, resume, commit = _make_callbacks(log)

    async def feed_low_vad() -> None:
        await asyncio.sleep(0.005)
        while engine.is_verifying:
            engine.note_vad(0.1)
            await asyncio.sleep(0.01)

    feeder = asyncio.create_task(feed_low_vad())
    decision = await engine.run(pause=pause, resume=resume, commit=commit)
    await feeder

    assert decision.committed is False
    assert decision.reason == "false_alarm_resumed"
    assert log.pause == ["pause"]
    assert log.resume == ["resume"]
    assert log.commit == []


@pytest.mark.asyncio
async def test_sustained_high_vad_commits() -> None:
    engine = BargeVerifyEngine(_test_config())
    log = BargeCallLog()
    pause, resume, commit = _make_callbacks(log)

    async def feed_high_vad() -> None:
        await asyncio.sleep(0.005)
        while engine.is_verifying:
            engine.note_vad(0.9)
            await asyncio.sleep(0.01)

    feeder = asyncio.create_task(feed_high_vad())
    decision = await engine.run(pause=pause, resume=resume, commit=commit)
    await feeder

    assert decision.committed is True
    assert decision.reason == "sustained_speech_confirmed"
    assert decision.sustained_speech_ms >= 30.0
    assert log.pause == ["pause"]
    assert log.commit == ["commit"]
    assert log.resume == []


@pytest.mark.asyncio
async def test_partial_four_words_commits_without_sustained_vad() -> None:
    engine = BargeVerifyEngine(_test_config())
    log = BargeCallLog()
    pause, resume, commit = _make_callbacks(log)

    async def feed_partial() -> None:
        await asyncio.sleep(0.005)
        engine.note_partial("wait stop right now")

    feeder = asyncio.create_task(feed_partial())
    decision = await engine.run(pause=pause, resume=resume, commit=commit)
    await feeder

    assert decision.committed is True
    assert decision.partial_words >= 4
    assert decision.sustained_speech_ms == 0.0
    assert log.commit == ["commit"]
    assert log.resume == []
