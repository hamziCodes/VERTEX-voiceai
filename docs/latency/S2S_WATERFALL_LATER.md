# Speech-to-Speech (S2S) Latency Waterfall Specification [LATER]

## Overview
This document specifies the deferred S2S direct speech-to-speech latency waterfall metrics.

## Future Architecture
- Direct S2S model input/output timestamps bypass cascaded STT -> LLM -> TTS stages.
- Target S2S TTFB latency budget: < 300 ms.
