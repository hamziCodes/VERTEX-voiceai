"""Wavia Python SDK quickstart: mint a session, say hello, hear the agent.

Run against a local engine (control plane on :8000, worker on :8081) started
in development demo mode, or point it at your own deployment::

    pip install ucve-voice-sdk
    python quickstart.py --control-plane http://127.0.0.1:8000

In production the mint call belongs in your authenticated backend, using a
tenant API key with the ``session:mint`` scope (``--api-key`` here); the
browser or device only ever receives the short-lived session token.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.request

from ucve import UCVEVoiceClient

DEMO_TENANT = "00000000-0000-0000-0000-000000000001"
DEMO_AGENT = "00000000-0000-0000-0000-0000000000a1"


def mint_session(control_plane: str, tenant: str, agent: str, api_key: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        f"{control_plane.rstrip('/')}/v1/session/mint",
        data=json.dumps({"tenant_id": tenant, "agent_id": agent}).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return json.load(response)


async def run(args: argparse.Namespace) -> int:
    session = mint_session(args.control_plane, args.tenant, args.agent, args.api_key)
    agent_text: list[str] = []
    audio_bytes = 0
    replied = asyncio.Event()

    def on_transcript(speaker: str, text: str) -> None:
        if speaker != "user" and text:
            agent_text.append(text)
            print(f"agent: {text}")

    def on_audio(chunk: bytes) -> None:
        nonlocal audio_bytes
        audio_bytes += len(chunk)
        if audio_bytes >= 3200:  # 100 ms of 16 kHz PCM16
            replied.set()

    def on_error(event: dict) -> None:
        print(f"error: {event}", file=sys.stderr)

    client = UCVEVoiceClient(
        token=session["token"],
        ws_url=args.ws_url or session["ws_url"],
        on_transcript=on_transcript,
        on_audio=on_audio,
        on_error=on_error,
    )
    await client.connect()
    try:
        await client.send_text_turn("Hello, what can you help me with?")
        await asyncio.wait_for(replied.wait(), timeout=args.timeout)
    except TimeoutError:
        print("no agent audio before the timeout", file=sys.stderr)
        return 1
    finally:
        await client.disconnect()
    print(f"received {audio_bytes} bytes of agent audio")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-plane", default="http://127.0.0.1:8000")
    parser.add_argument("--ws-url", help="override the worker URL returned by mint")
    parser.add_argument("--tenant", default=DEMO_TENANT)
    parser.add_argument("--agent", default=DEMO_AGENT)
    parser.add_argument("--api-key", help="tenant API key with session:mint scope")
    parser.add_argument("--timeout", type=float, default=20.0)
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
