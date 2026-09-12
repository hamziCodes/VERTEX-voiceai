"""UCVE Sovereign Voice Client (Async Python)."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable

import websockets

from sdk.python.ucve.version import SDK_VERSION_MANIFEST, __version__


class UCVEVoiceClient:
    """Async client for connecting to sovereign UCVE realtime audio streaming sessions.

    Strict zero-secret pattern: accepts only an ephemeral session token minted by
    your host backend. Raw tenant or provider API keys are strictly rejected.
    """

    def __init__(
        self,
        token: str,
        ws_url: str = "ws://localhost:8081/ws/audio",
        *,
        stt_provider: str = "gladia",
        llm_provider: str = "groq",
        tts_provider: str = "cartesia",
        on_transcript: Callable[[str, str], Any] | None = None,
        on_audio: Callable[[bytes], Any] | None = None,
        on_metric: Callable[[dict[str, Any]], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        # Strict zero-secret constructor validation
        for forbidden in ("api_key", "secret", "private_key", "tenant_secret"):
            if forbidden in kwargs or forbidden in token.lower() and "=" in token:
                raise ValueError(
                    f"Client SDK must never accept raw '{forbidden}'. "
                    "Mint an ephemeral session token on your host backend instead."
                )

        if not token or not token.strip():
            raise ValueError("An ephemeral session token is required to initialize UCVEVoiceClient.")

        self.token = token.strip()
        self.ws_url = ws_url.strip()
        self.stt_provider = stt_provider
        self.llm_provider = llm_provider
        self.tts_provider = tts_provider
        self.on_transcript = on_transcript
        self.on_audio = on_audio
        self.on_metric = on_metric
        self._ws: Any | None = None
        self._running = False
        self.version_manifest = SDK_VERSION_MANIFEST

    async def connect(self) -> None:
        """Establish Sovereign WebSocket connection."""
        url = self.ws_url
        separator = "&" if "?" in url else "?"
        query = (
            f"token={self.token}"
            f"&stt_provider={self.stt_provider}"
            f"&llm_provider={self.llm_provider}"
            f"&tts_provider={self.tts_provider}"
        )
        full_url = f"{url}{separator}{query}"
        self._ws = await websockets.connect(full_url)
        self._running = True

    async def send_audio(self, pcm16_bytes: bytes) -> None:
        """Stream a raw 16 kHz mono 16-bit PCM chunk to the voice pipeline."""
        if not self._ws:
            raise RuntimeError("Client is not connected. Call connect() first.")
        await self._ws.send(pcm16_bytes)

    async def emit_playback_started(self) -> None:
        """Notify pipeline that audio playback has begun on speakers (Phase 24 latency anchor)."""
        if not self._ws:
            return
        msg = {
            "event_type": "control.playback_started",
            "payload": {"t": time.time() * 1000, "kind": "playback_started"},
        }
        await self._ws.send(json.dumps(msg))

    async def send_barge_in(self, rms: float = 0.08) -> None:
        """Trigger instant voice barge-in cancellation."""
        if not self._ws:
            return
        msg = {
            "event_type": "control.barge_in",
            "payload": {"rms": rms, "t": time.time() * 1000},
        }
        await self._ws.send(json.dumps(msg))

    async def disconnect(self) -> None:
        """Gracefully close the streaming session."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
