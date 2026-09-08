"""Sovereign Direct SIP Transport — Direct PSTN RTP media piping into PipelineOrchestrator."""

from __future__ import annotations

import asyncio
from typing import Any, Callable
from uuid import UUID

from core.transport.caller_id import CallerIdContext
from telephony_gateway.transcoding.mulaw import (
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    resample_pcm16_16k_to_8k,
    resample_pcm16_8k_to_16k,
)
from telephony_gateway.transcoding.rebuffer import TelephonyRebuffer


class DirectSIPTransport:
    """Sovereign Direct SIP Transport — Inbound RTP -> μ-law decode -> 16kHz PCM16 -> Pipeline."""

    def __init__(
        self,
        session_id: UUID,
        caller_id: CallerIdContext,
        on_audio_frame: Callable[[bytes], Any] | None = None,
        on_mulaw_egress: Callable[[bytes], Any] | None = None,
    ) -> None:
        self.session_id = session_id
        self.caller_id = caller_id
        self.on_audio_frame = on_audio_frame
        self.on_mulaw_egress = on_mulaw_egress
        self.rebuffer = TelephonyRebuffer(target_samples_per_frame=512)
        self.active = True
        self.total_bytes_received = 0
        self.total_frames_emitted = 0
        self.total_bytes_sent = 0

    async def receive_mulaw_frame(self, mulaw_bytes: bytes) -> list[bytes]:
        """Process incoming 20 ms μ-law RTP payload from SIP trunk.

        1. G.711 μ-law decode (8 kHz) -> PCM16 (8 kHz)
        2. Resample 8 kHz -> 16 kHz PCM16
        3. Rebuffer to 512-sample canonical frames
        """
        if not self.active:
            return []

        self.total_bytes_received += len(mulaw_bytes)

        # 1. Decode μ-law to 8kHz PCM16
        pcm8k = mulaw_to_pcm16(mulaw_bytes)

        # 2. Resample 8kHz PCM16 to 16kHz PCM16
        pcm16k = resample_pcm16_8k_to_16k(pcm8k)

        # 3. Rebuffer to 512-sample (1024-byte) frames
        canonical_frames = self.rebuffer.push(pcm16k)
        self.total_frames_emitted += len(canonical_frames)

        if self.on_audio_frame:
            for frame in canonical_frames:
                res = self.on_audio_frame(frame)
                if asyncio.iscoroutine(res):
                    await res

        return canonical_frames

    async def send_pcm16_frame(self, pcm16_16k: bytes) -> bytes:
        """Encode 16 kHz PCM16 agent audio for SIP RTP egress (μ-law @ 8 kHz).

        1. Downsample 16 kHz PCM16 -> 8 kHz PCM16
        2. G.711 μ-law encode
        3. Invoke ``on_mulaw_egress`` callback (RTP layer hooks here)
        """
        if not self.active or not pcm16_16k:
            return b""

        pcm8k = resample_pcm16_16k_to_8k(pcm16_16k)
        mulaw_bytes = pcm16_to_mulaw(pcm8k)
        if not mulaw_bytes:
            return b""

        self.total_bytes_sent += len(mulaw_bytes)

        if self.on_mulaw_egress:
            res = self.on_mulaw_egress(mulaw_bytes)
            if asyncio.iscoroutine(res):
                await res

        return mulaw_bytes

    async def close(self) -> None:
        """Teardown Direct SIP leg."""
        self.active = False
