"""Offline worker load harness (Phase 14).

Starts the real worker in a child process (mock providers, no network),
opens N concurrent WebSocket sessions that stream 16 kHz PCM at real-time
pace (speech bursts and pauses), and measures against the runtime profile:

- worker startup time to readiness;
- sessions admitted / refused (and the close codes);
- per-turn time from the end of a speech burst to the first returned audio
  byte as observed by the client (mock providers: this measures the engine's
  own overhead, not provider latency);
- worker resident memory (sampled peak) and CPU utilisation;
- worker event-loop lag p99 and buffer drops from its own /metrics.

Usage::

    python -m tests.scaling.load_harness --sessions 5 --seconds 20 --profile dev

Writes a JSON report to stdout (and ``--out`` if given).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import websockets

from tests.scaling.procstats import rss_and_cpu

REPO = Path(__file__).resolve().parents[2]
SAMPLE_RATE = 16000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


DEFAULT_SPEECH_WAV = (
    REPO / "legacy_codebases" / "habiba-sdk-agent" / "tests" / "out_uplift_smoke.wav"
)


def load_speech_pcm16k(path: Path) -> bytes:
    """Read a mono 16-bit WAV and resample it linearly to 16 kHz PCM16."""
    import wave

    import numpy as np

    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("speech fixture must be mono 16-bit PCM")
        rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    if rate != SAMPLE_RATE:
        duration = len(samples) / rate
        target = np.linspace(0, len(samples) - 1, int(duration * SAMPLE_RATE))
        samples = np.interp(target, np.arange(len(samples)), samples).astype("<i2")
    return samples.astype("<i2").tobytes()


def _frame(t0: int, speech: bool) -> bytes:
    """A 20 ms PCM16 frame: voiced harmonics for speech, near-silence otherwise."""
    samples = []
    for i in range(FRAME_SAMPLES):
        n = t0 + i
        if speech:
            value = 0.25 * math.sin(2 * math.pi * 180 * n / SAMPLE_RATE)
            value += 0.12 * math.sin(2 * math.pi * 360 * n / SAMPLE_RATE)
            value += 0.06 * math.sin(2 * math.pi * 720 * n / SAMPLE_RATE)
            value *= 0.6 + 0.4 * math.sin(2 * math.pi * 4 * n / SAMPLE_RATE)
        else:
            value = 0.0005 * math.sin(2 * math.pi * 50 * n / SAMPLE_RATE)
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))
    return struct.pack(f"<{FRAME_SAMPLES}h", *samples)


@dataclass
class SessionResult:
    ok: bool = False
    close_code: int | None = None
    error: str | None = None
    turns: int = 0
    audio_bytes: int = 0
    first_audio_ms: list[float] = field(default_factory=list)


async def _session(
    url: str, seconds: float, speech: bytes, pause_s: float
) -> SessionResult:
    result = SessionResult()
    try:
        async with websockets.connect(url, max_size=2**20, open_timeout=10) as ws:
            await ws.send(
                json.dumps(
                    {
                        "event_type": "protocol.hello",
                        "protocol_version": "1.0.0",
                        "event_id": "hello-1",
                        "sequence": 1,
                        "payload": {
                            "protocol_version": "1.0.0",
                            "sdk": {"name": "load-harness", "version": "1.0.0"},
                        },
                    }
                )
            )
            speech_end: float | None = None
            awaiting = False

            async def receiver() -> None:
                nonlocal awaiting
                async for message in ws:
                    if isinstance(message, bytes):
                        result.audio_bytes += len(message)
                        if awaiting and speech_end is not None:
                            result.first_audio_ms.append(
                                (time.perf_counter() - speech_end) * 1000.0
                            )
                            awaiting = False

            recv_task = asyncio.create_task(receiver())
            start = time.perf_counter()
            frame_bytes = FRAME_SAMPLES * 2
            speech_frames = [
                speech[i : i + frame_bytes].ljust(frame_bytes, b"\x00")
                for i in range(0, len(speech), frame_bytes)
            ]
            pause_frames = int(pause_s * 1000 / FRAME_MS)
            cycle = [*speech_frames, *([None] * pause_frames)]
            frame_index = 0
            sample_index = 0
            while time.perf_counter() - start < seconds:
                position = frame_index % len(cycle)
                chunk = cycle[position]
                if chunk is None:
                    if position == len(speech_frames):
                        speech_end = time.perf_counter()
                        awaiting = True
                        result.turns += 1
                    chunk = _frame(sample_index, False)
                await ws.send(chunk)
                sample_index += FRAME_SAMPLES
                frame_index += 1
                target = start + frame_index * FRAME_MS / 1000.0
                await asyncio.sleep(max(0.0, target - time.perf_counter()))
            await ws.send(
                json.dumps(
                    {
                        "event_type": "session.close",
                        "protocol_version": "1.0.0",
                        "event_id": "close-1",
                        "sequence": 2,
                        "payload": {},
                    }
                )
            )
            await asyncio.sleep(0.5)
            recv_task.cancel()
            result.ok = True
            result.close_code = ws.close_code
    except websockets.ConnectionClosed as exc:
        result.close_code = exc.rcvd.code if exc.rcvd else None
        result.error = "closed"
    except Exception as exc:  # noqa: BLE001 - recorded in the report
        result.error = type(exc).__name__
    return result


def _histogram_quantile(metrics: str, name: str, q: float) -> float | None:
    buckets: dict[float, float] = {}
    pattern = re.compile(rf'^{name}_bucket\{{[^}}]*le="([^"]+)"\}} ([0-9.e+-]+)$')
    for line in metrics.splitlines():
        match = pattern.match(line)
        if match:
            le = math.inf if match.group(1) == "+Inf" else float(match.group(1))
            buckets[le] = buckets.get(le, 0.0) + float(match.group(2))
    if not buckets or buckets.get(math.inf, 0.0) == 0:
        return None
    total = buckets[math.inf]
    rank = q * total
    previous_bound, previous_count = 0.0, 0.0
    for bound in sorted(buckets):
        count = buckets[bound]
        if count >= rank:
            if math.isinf(bound):
                return previous_bound
            span = count - previous_count
            if span == 0:
                return bound
            return (
                previous_bound
                + (bound - previous_bound) * (rank - previous_count) / span
            )
        previous_bound, previous_count = bound, count
    return None


def _counter_total(metrics: str, name: str) -> float:
    total = 0.0
    for line in metrics.splitlines():
        if line.startswith(name + "{") or line.startswith(name + " "):
            total += float(line.rsplit(" ", 1)[1])
    return total


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return round(ordered[index], 1)


async def run(
    sessions: int,
    seconds: float,
    profile: str,
    pause_s: float,
    speech_wav: Path = DEFAULT_SPEECH_WAV,
) -> dict[str, Any]:
    speech = load_speech_pcm16k(speech_wav)
    port = _free_port()
    bearer = "load-harness-bearer"
    env = {
        **os.environ,
        "UCVE_ENV": "development",
        "UCVE_DEMO_MODE": "0",
        "RUN_MOCK_PROVIDERS": "1",
        "RUN_LIVE_PROVIDERS": "0",
        "RUN_LIVE_TELEPHONY": "0",
        "UCVE_STT_MOCK_TEXT": "I would like to book an appointment",
        "UCVE_RUNTIME_PROFILE": profile,
        "UCVE_METRICS_BEARER": bearer,
        "UCVE_USE_MEMORY_REPOS": "1",
        "OTEL_EXPORTER_ENABLED": "false",
        "OMP_NUM_THREADS": "1",
        "LOADTEST_STACKDUMP_S": os.environ.get("LOADTEST_STACKDUMP_S", "0"),
        "LOADTEST_STACKDUMP_FILE": os.environ.get("LOADTEST_STACKDUMP_FILE", ""),
        "PYTHONASYNCIODEBUG": os.environ.get("PYTHONASYNCIODEBUG", ""),
        "LOADTEST_SLOW_CALLBACK_MS": os.environ.get("LOADTEST_SLOW_CALLBACK_MS", ""),
    }
    # Empty (not absent) so a developer .env loaded by the app cannot re-add them.
    env["DATABASE_URL"] = ""
    env["REDIS_URL"] = ""
    started = time.perf_counter()
    # A file, not a pipe: an unread pipe fills up and blocks the worker's
    # event loop inside its log handler.
    log_file = tempfile.NamedTemporaryFile(  # noqa: SIM115 - closed in finally
        prefix="wavia-load-", suffix=".log", delete=False
    )
    child = subprocess.Popen(
        [sys.executable, "-m", "tests.scaling.worker_bootstrap", "--port", str(port)],
        cwd=REPO,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    report: dict[str, Any] = {"profile": profile, "sessions_requested": sessions}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            ready_status = None
            for _ in range(240):
                try:
                    response = await client.get(f"{base}/health/ready")
                    ready_status = response.status_code
                    if ready_status == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.25)
            report["startup_to_ready_s"] = round(time.perf_counter() - started, 2)
            report["ready_status"] = ready_status
            if ready_status != 200:
                raise RuntimeError("worker did not become ready")
            worker_pid = int((await client.get(f"{base}/__loadtest/pid")).json()["pid"])
            rss_idle, cpu_idle = rss_and_cpu(worker_pid)
            tokens = []
            for index in range(sessions):
                # Five sessions per synthetic tenant keeps every tenant inside
                # its plan's concurrency quota, so the worker is what is tested.
                body = (
                    await client.post(f"{base}/__loadtest/mint?tenant={index // 5}")
                ).json()
                tokens.append(body.get("token"))
            report["mint_refused"] = sum(1 for t in tokens if not t)

            peak_rss = rss_idle
            sampling = True

            async def sample() -> None:
                nonlocal peak_rss
                while sampling:
                    peak_rss = max(peak_rss, rss_and_cpu(worker_pid)[0])
                    await asyncio.sleep(0.5)

            sampler = asyncio.create_task(sample())
            run_start = time.perf_counter()
            results = await asyncio.gather(
                *(
                    _session(
                        f"ws://127.0.0.1:{port}/ws/audio?token={token}&sample_rate=16000",
                        seconds,
                        speech,
                        pause_s,
                    )
                    for token in tokens
                    if token
                )
            )
            wall = time.perf_counter() - run_start
            sampling = False
            await sampler
            rss_end, cpu_end = rss_and_cpu(worker_pid)
            metrics = ""
            for attempt in range(3):
                try:
                    metrics = (
                        await client.get(
                            f"{base}/metrics",
                            headers={"Authorization": f"Bearer {bearer}"},
                            timeout=30.0,
                        )
                    ).text
                    break
                except httpx.HTTPError as exc:
                    report.setdefault("metrics_errors", []).append(
                        f"{attempt}:{type(exc).__name__}"
                    )
    finally:
        child.terminate()
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        log_file.close()
        log_text = Path(log_file.name).read_text(encoding="utf-8", errors="replace")
        report["worker_log_errors"] = [
            line
            for line in log_text.splitlines()
            if "Error" in line or "Exception" in line
        ][-20:]
        report["worker_log_path"] = log_file.name

    first_audio = [v for r in results for v in r.first_audio_ms]
    turns = sum(r.turns for r in results)
    report.update(
        {
            "sessions_completed": sum(1 for r in results if r.ok),
            "session_errors": sorted({r.error for r in results if r.error}),
            "close_codes": sorted({r.close_code for r in results if r.close_code}),
            "duration_s": round(wall, 1),
            "turns_spoken": turns,
            "turns_with_audio_reply": len(first_audio),
            "client_first_audio_ms": {
                "p50": _percentile(first_audio, 0.50),
                "p95": _percentile(first_audio, 0.95),
                "p99": _percentile(first_audio, 0.99),
            },
            "audio_out_bytes": sum(r.audio_bytes for r in results),
            "worker_rss_mb": {
                "idle": round(rss_idle / 2**20, 1),
                "peak": round(peak_rss / 2**20, 1),
                "end": round(rss_end / 2**20, 1),
            },
            "worker_cpu_percent_of_one_core": round(
                100.0 * (cpu_end - cpu_idle) / max(wall, 1e-6), 1
            ),
            "event_loop_lag_ms": {
                "p50": _histogram_quantile(metrics, "ucve_event_loop_lag_ms", 0.5),
                "p99": _histogram_quantile(metrics, "ucve_event_loop_lag_ms", 0.99),
            },
            "buffer_drops": _counter_total(metrics, "ucve_buffer_drop_total"),
            "barge_ins": _counter_total(metrics, "ucve_barge_in_total"),
            "metric_turn_latency_p95_ms": _histogram_quantile(
                metrics, "ucve_turn_latency_ms", 0.95
            ),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=5)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--profile", default="dev")
    parser.add_argument("--pause-s", type=float, default=2.5)
    parser.add_argument("--speech-wav", type=Path, default=DEFAULT_SPEECH_WAV)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    report = asyncio.run(
        run(args.sessions, args.seconds, args.profile, args.pause_s, args.speech_wav)
    )
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
