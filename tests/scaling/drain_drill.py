"""Drain drill: SIGTERM/CTRL_BREAK during a live session (Phase 14).

Starts the worker (mock providers), opens one streaming session, signals the
process, then checks: readiness reports draining, a new session is refused
with 1013, the live session keeps streaming to its natural end, and the
process exits on its own after it.

    python -m tests.scaling.drain_drill
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time

import httpx
import websockets

from tests.scaling.load_harness import (
    DEFAULT_SPEECH_WAV,
    REPO,
    _free_port,
    _session,
    load_speech_pcm16k,
)


async def drill(session_seconds: float = 10.0, signal_after_s: float = 3.0) -> dict:
    port = _free_port()
    env = {
        **os.environ,
        "UCVE_ENV": "development",
        "RUN_MOCK_PROVIDERS": "1",
        "UCVE_STT_MOCK_TEXT": "I would like to book an appointment",
        "UCVE_METRICS_BEARER": "drill",
        "DATABASE_URL": "",
        "REDIS_URL": "",
        "WAVIA_DRAIN_TIMEOUT_S": "60",
        "OMP_NUM_THREADS": "1",
    }
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    child = subprocess.Popen(
        [sys.executable, "-m", "tests.scaling.worker_bootstrap", "--port", str(port)],
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    base = f"http://127.0.0.1:{port}"
    report: dict = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for _ in range(120):
            try:
                if (await client.get(f"{base}/health/ready")).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.25)
        token = (await client.post(f"{base}/__loadtest/mint")).json()["token"]
        spare = (await client.post(f"{base}/__loadtest/mint?tenant=1")).json()["token"]
        speech = load_speech_pcm16k(DEFAULT_SPEECH_WAV)
        live = asyncio.create_task(
            _session(
                f"ws://127.0.0.1:{port}/ws/audio?token={token}&sample_rate=16000",
                session_seconds,
                speech,
                2.0,
            )
        )
        await asyncio.sleep(signal_after_s)
        signalled_at = time.perf_counter()
        if sys.platform == "win32":
            child.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            child.send_signal(signal.SIGTERM)
        await asyncio.sleep(0.5)
        ready = await client.get(f"{base}/health/ready")
        report["ready_after_signal"] = [ready.status_code, ready.json()["status"]]
        try:
            async with websockets.connect(
                f"ws://127.0.0.1:{port}/ws/audio?token={spare}&sample_rate=16000"
            ) as ws:
                await ws.recv()
            report["new_session"] = "accepted"
        except websockets.ConnectionClosed as exc:
            report["new_session"] = f"refused {exc.rcvd.code if exc.rcvd else None}"
        except websockets.InvalidStatus as exc:
            report["new_session"] = f"refused HTTP {exc.response.status_code}"
        result = await live
        report["live_session"] = {
            "completed": result.ok,
            "turns": result.turns,
            "replies": len(result.first_audio_ms),
            "audio_bytes": result.audio_bytes,
        }
    exit_code = await asyncio.to_thread(child.wait, 90)
    report["process_exit_code"] = exit_code
    report["exit_after_signal_s"] = round(time.perf_counter() - signalled_at, 1)
    return report


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(json.dumps(asyncio.run(drill()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
