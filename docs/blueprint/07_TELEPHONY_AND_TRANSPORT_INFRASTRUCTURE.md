# 07 — Telephony & Transport Infrastructure

File 7 of 9. Companion to File 1 §3.4 (the `BaseTransportGateway` abstraction) — this file details the concrete adapters, with special attention to what the audits actually found versus what the original project naming *claimed*. Two of the four repos had their telephony claims directly contradicted by static analysis, which is exactly the kind of thing this file must not repeat.

---

## 1. Ground Truth Correction (read this before building anything)

The original audit protocol assumed `awazlabs` had "enterprise-grade... barge-in, WebSocket session lifecycle" and `habiba-sdk-agent` had "Dual-layer telephony (SIP/Twilio/Asterisk)." Neither held up under inspection:

- **awaazlabs has zero telephony transport code.** It receives Retell AI's *post-call* webhooks; Retell owns the entire real-time voice/telephony leg externally (AUDIT_02 §1: "Inbound voice is owned by Retell AI (external)... Audio never enters this codebase as PCM"). There is no SIP, no WebSocket audio, no TwiML in this repo (AUDIT_02 §4: "NOT IMPLEMENTED / ABSENT" for TwiML/Twilio Media Streams and SIP/Asterisk both).
- **habiba-sdk-agent's telephony is Telnyx + LiveKit SIP, not Twilio/Asterisk.** A repo-wide grep for `twilio|asterisk` returned zero matches (AUDIT_04 §1 scope note, header). The real path is Telnyx PSTN trunks terminating as SIP participants inside LiveKit rooms (AUDIT_04 §1 dependency diagram: "Telnyx[Telnyx PSTN] -->|SIP| LK[LiveKit Cloud]").

**Implication for UCVE:** `TwilioMediaStreamTransport` and a LiveKit-free `DirectSIPTransport` are new build work. Habiba informs Telnyx webhook auth and DID→agent resolve (AUDIT_04 §3 step 9), not a requirement to keep LiveKit on the call path. Do not assume Twilio-specific code exists in the audited trees to port from.

---

## 2. Audio Transcoding Pipelines

### 2.1 μ-law ↔ PCM16 (telephony leg)

None of the four repos implement this — it's a pure gap (File 1 §3.4 adapter table). Standard G.711 μ-law/A-law expansion tables apply; the only design decision worth stating explicitly is *where* this happens:

```python
class TelephonyTranscoder:
    """Lives inside DirectSIPTransport / TwilioMediaStreamTransport
    (File 1 §3.4), NOT inside the shared pipeline core. The pipeline core
    (File 2/3) only ever sees canonical 16kHz PCM16 — transcoding is a
    transport-adapter responsibility, matching the principle that
    BaseTransportGateway normalizes wire format before anything reaches
    VAD/STT (File 1 §3.4: 'pipeline core never imports a transport-specific
    type')."""

    @staticmethod
    def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes: ...   # G.711 expand table

    @staticmethod
    def pcm16_to_mulaw(pcm16_bytes: bytes) -> bytes: ...   # G.711 compress table

    @staticmethod
    def upsample_8k_to_16k(pcm16_8k: bytes) -> bytes: ...   # File 2 §1.2 Resampler

    @staticmethod
    def downsample_16k_to_8k(pcm16_16k: bytes) -> bytes: ...
```

### 2.2 Frame size reconciliation

Telephony legs (Twilio Media Streams, generic SIP/RTP) typically deliver 20ms frames at 8kHz (160 bytes μ-law). UCVE's canonical internal frame is 512 samples/32ms at 16kHz (File 2 §1.3, matching v3's Silero-aligned chunking, AUDIT_01 §2). The transcoder must therefore also **rebuffer**, not just resample — accumulating telephony frames until a full canonical frame is available, rather than emitting mismatched-size frames into the VAD/STT pipeline.

---

## 3. WebRTC Signaling & Media Flow

### 3.1 Optional managed media plane (LiveKit / future SFU) — harvested from habiba, not load-bearing

Habiba's production WebRTC path is LiveKit Cloud (AUDIT_04 §1). UCVE **may** run that path as a `LiveKitWebRTCTransport` adapter. It is **not** required to place a call (File 1 §1, §3.6).

| Component | Habiba pattern | UCVE posture |
|---|---|---|
| SFU | LiveKit Cloud (external managed service) | Optional. `MediaSFUAdapter` so Daily or self-hosted LiveKit OSS / mediasoup is a peer later. AUDIT_05 §3: no in-repo SFU in any of the four — we do not invent one for v1, and we do not make Cloud SFU the product. |
| Session token | Short-TTL (120s) room-join-only JWT | Used only when this adapter is selected |
| Client join | `livekit-client` Room connect (`sdk/src/index.ts:198–202`) | Sovereign SDK speaks UCVE events (File 8 §3) over native WS first; LiveKit client is an optional transport backend |
| Data channels | Habiba `metrics_updated` → UCVE `metric` | Same vocabulary on every adapter |
| ICE/STUN/TURN | LiveKit Cloud | If this adapter is off, N/A; if on, still not in-repo (AUDIT_04 §2) |

### 3.2 Raw plane (custom WebSocket) — adopted from v3/multilingual

| Component | Pattern | Citation |
|---|---|---|
| Signaling | None — direct WS upgrade, no SDP negotiation (this is raw PCM over WS, not real WebRTC) | AUDIT_01 §3 handshake; AUDIT_03 handshake (parallel structure) |
| Capture | Browser `getUserMedia` + AudioWorklet, 16kHz mono, echo cancellation/noise suppression/AGC on | AUDIT_01 §2: `channelCount:1, echoCancellation/noiseSuppression/autoGainControl true` |
| Playback | AudioWorklet PCM player with jitter prebuffer | AUDIT_01 §2 (3-chunk prebuffer — see File 2 §1.3 note that this should shrink for the 450ms target) |
| Heartbeat | Server ping every 20s | AUDIT_01 §4 WS catalog; AUDIT_03 §4 (identical) |
| **Known gap to fix** | Neither v3 nor multilingual implements a client pong handler or reconnect logic (AUDIT_01 §5: "Client pong / reconnect: NOT IMPLEMENTED / ABSENT"; AUDIT_03 §5 heartbeat: "client pong ABSENT") | UCVE's `NativeWebSocketTransport` client implements pong response and automatic reconnect with session resumption (via the Redis-backed session state, File 1 §3.3) |

---

## 4. SIP Trunk Gateway

### 4.1 Adopted from habiba/Telnyx — generalized to dual-home trunks

Habiba's live dialer is Telnyx-edged LiveKit SIP (AUDIT_04 §4; `telephony_service.py:999–1183`). UCVE keeps that as **one** `DirectSIPTransport` configuration, not the only trunk. File 1 §3.6: production telephony requires two independently reachable SIP destinations (Telnyx + `generic_pta` / Twilio SIP / second Telnyx account in another region). DID inventory may stay on Telnyx; call completion must not.

```python
class SIPTrunkConfig(BaseModel):
    provider: Literal["telnyx", "generic_pta", "twilio_sip"]
    trunk_credentials_ref: str                     # secrets-layer reference, never
                                                     # inline (File 3 §6 anti-pattern)
    webhook_public_key: str | None = None            # Telnyx public-key webhook
                                                     # verification, AUDIT_04 §4
    priority: int = 0                                # FailoverRouter-equivalent for PSTN
    role: Literal["primary", "secondary"] = "primary"


class SIPParticipantResolver:
    """Resolves an inbound SIP call to (tenant_id, agent_id) via DID lookup,
    falling back to job-dispatch metadata or JWT claim — exact fallback
    chain from habiba: 'dispatch job -> SIP DB -> JWT metadata'
    (AUDIT_04 §3 handshake step 9)."""

    async def resolve(self, sip_headers: dict) -> tuple[str, str]: ...
```

### 4.2 Outbound / warm transfer

**Gap identified:** warm transfer, supervisor whisper, AMD/voicemail-drop campaign orchestration, and calling-window compliance gates are not implemented in any of the four trees. Habiba **does** implement a **one-shot outbound PSTN dialer** that is LiveKit-coupled: `create_outbound_call` (`telephony_service.py:999–1183`) dispatches a named LiveKit worker then `create_sip_participant` toward a Telnyx edge. That is **one** adapter. UCVE's sovereign outbound path is `DirectSIPTransport` placing the call from `worker-raw` without LiveKit (File 1 §3.6). Telnyx remains inventory/SIP plumbing, not `/v2/calls`. `escalate_to_human` today only inserts `escalations` (`worker/tools.py:91–113`) — SIP bridge is `[NEW]`.

```python
class WarmTransferService:
    """Escalate_to_human (File 6 §2.2 builtin tool) triggers this. Bridges
    the active LiveKit room (or raw-plane call) to a human agent's SIP
    endpoint while keeping the AI agent on the line in a listening/whisper
    capacity until the human explicitly takes over."""

    async def initiate_transfer(self, session_id: str, target_sip_uri: str, whisper_context: str) -> None: ...
```

```python
class OutboundCampaign(BaseModel):
    campaign_id: str
    tenant_id: str
    dial_list: list[str]                       # E.164 numbers
    amd_enabled: bool = True                    # Answering Machine Detection
    voicemail_drop_audio_id: str | None = None
    calling_window: "CallingWindow"              # compliance-enforced hours


class CallingWindow(BaseModel):
    timezone: str
    start_hour: int = 9
    end_hour: int = 20
    days_of_week: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    # Enforced server-side before dial, not left to campaign operator
    # discipline — relevant given zero compliance tooling exists in any
    # audited repo (File 5 §9 compliance gap applies equally here).
```

---

## 5. Live Call Monitoring

`[NEW]` — no legacy repo has a supervisor-facing live view; awaazlabs' dashboard shows *post-call* data (bookings, transcripts, escalations as historical records, AUDIT_02 §1 directory tree: `app/(dashboard)/`) not a live audio/sentiment stream during an active call.

```python
class LiveMonitorFeed:
    """Supervisor dashboard subscribes to this per active session. Reuses
    the same control-event vocabulary as File 8 §3 (`control.barge_in`,
    `control.hangup`, `metric`, …) via the transport gateway's
    send_control (File 1 §3.4) — a supervisor client is architecturally
    just another consumer of the session's event stream, read-only except
    for the whisper/barge channel."""

    async def subscribe(self, session_id: str, supervisor_id: str) -> "AsyncIterator[LiveMonitorEvent]": ...
    async def whisper(self, session_id: str, supervisor_id: str, audio_frame: bytes) -> None:
        """Audio injected to the AI-agent-side channel only, not audible to
        the caller — requires the transport adapter to support a private
        mixing bus, available natively in LiveKit (managed plane) and
        requiring explicit dual-bus handling in the raw plane."""
```

---

## 6. Telephony Compliance Enforcement Point

Ties back to File 5 §9: `CallingWindow` (§4.2 above) and consent/recording-disclosure requirements are enforced at the SIP gateway / outbound dialer layer — before a call connects — not retrofitted post-call. This is the one place in the whole blueprint where compliance is a **transport-layer gate**, not a post-processing concern, because outbound-calling-window violations and missing recording disclosure are illegal at time of dial, not fixable after the fact.
