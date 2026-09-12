# UCVE Flutter SDK — Architecture Roadmap (Post-v1 Milestones)

## 1. Executive Summary
In accordance with Phase 28 specifications, web and TypeScript/Python SDKs constitute the primary developer surface for v1.
The Flutter SDK (`sdk/flutter/`) is established as a **roadmap item and interface stub** and is **not a blocker for v1 production release.**

---

## 2. Planned Milestones

### Milestone 1: Cross-Platform Native Audio Streaming (Q4)
- Port Web Audio Worklet downsampling (16 kHz PCM) to Flutter platform channels:
  - iOS: `AVAudioEngine` input node (16-bit linear PCM mono buffer streaming).
  - Android: `AudioRecord` with `AudioFormat.ENCODING_PCM_16BIT`.
- Low-latency binary WebSocket transport with automatic reconnection.

### Milestone 2: Background Call Handling & OS Telecom Frameworks (Q1)
- Integration with native call managers:
  - iOS: `CallKit` provider for incoming call notifications and lock screen audio controls.
  - Android: `ConnectionService` integration.
- Hardware acoustic echo cancellation (AEC) and noise suppression hooks.

### Milestone 3: WebRTC / LiveKit Adapter Parity (Q2)
- Optional Flutter package parity matching `@ucve/voice-livekit`.
