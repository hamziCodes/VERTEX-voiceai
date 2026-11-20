# Why Wavia Feels Slower Than the Legacy Agents

## Short answer

The vendors are similar, but orchestration is not. Current Wavia adds waits before STT is ready, before it decides speech ended, before text reaches TTS, and before Uplift releases audio. Some measurements also describe server enqueue rather than what the caller hears. Reusing Gladia, Groq, and Uplift does not reproduce legacy latency unless connection timing, endpointing, text chunking, HTTP streaming, buffering, cancellation, and playback are equivalent.

## Latency budget

```text
actual speech ends
  + endpoint/VAD wait
  + STT finalization
  + retrieval/context work
  + LLM first token
  + wait for speakable text
  + TTS first audio byte
  + resampling/server queue/network/client prebuffer
= first audible reply
```

A 960 ms endpoint wait misses a subsecond goal before STT, LLM, or TTS begins.

## Direct code comparison

| Stage | Current Wavia | Proven legacy behavior | Effect |
|---|---|---|---|
| STT startup | Starts Gladia after VAD speech onset | Multilingual agent starts Gladia at session start | First utterance can pay connection setup and lose early audio |
| Endpoint | Defaults to 160 ms onset / 960 ms silence | Multilingual separates 200 ms UI response and 600 ms commit; Habiba measured 400 ms VAD stop as its clean winner | Current fallback path waits almost a second after speech |
| First LLM text | Waits for sentence punctuation or ≥9 words plus a pause; configured two-word option is unused | Multilingual chunker permits a first split after two words with language delimiters | Current TTS can wait for most of the answer |
| Uplift | `await client.post()` then `resp.content` | Multilingual iterates response network chunks from pooled `aiohttp` session | Current adapter chunks a completed body rather than streaming arrival |
| Warmth | First requests can be cold; STT is definitely late | Legacy pools TTS connections; Habiba prewarms components | DNS/TLS/setup becomes caller-visible |
| Playback | Marks playback at server enqueue; some resampling is stateless/lossy | Legacy sender tracks playout watermark; Habiba paces and records first audio | Metrics and perceived behavior disagree |
| Barge-in | Server cancel does not prove browser-scheduled audio stopped | Legacy sends client wipe, flushes queue, cancels TTS/LLM/tasks; Habiba asserts trailing audio/context | Agent can keep talking after interruption |
| Metrics | Worker/demo event fields disagree; some timestamps are substituted/capped | Habiba measures acoustic EOS→first audio with component metrics | Current optimization lacks a trustworthy baseline |

## Reuse policy

Reuse the patterns—warm streaming STT, language-aware early chunks, streaming HTTP reads, pooling, playout tracking, client buffer clearing, honest acoustic-end metrics. Do not paste legacy modules wholesale. Current Wavia has multi-tenant, provider, compliance, failover, SDK, and deployment constraints the smaller agents do not fully solve. Every borrowed behavior gets a regression test in the current architecture.

## Interpreting numbers

- VAD-end→audio-queued is internal processing, not perceived latency.
- STT-final→TTS-byte helps locate a stage but excludes endpoint and playback.
- Acoustic-end→first-audible-sample is the product metric.
- Offline fake providers isolate orchestration overhead; approved live runs measure vendors/network.
- Report sample count plus p50/p95/p99. Keep raw results and label exclusions.

## Fix sequence

1. Make timing truthful and turn-correlated.
2. Start live STT before speech and preserve pre-speech audio.
3. Tune endpointing on English, Urdu, mixed speech, pauses, and noise.
4. Release a safe first phrase after roughly two words or a language delimiter.
5. Stream TTS bytes on arrival and reuse connections.
6. Fix continuous resampling and actual playback acknowledgment.
7. Prove interruption stops provider, server, and browser buffers.
8. Only then run an approved live-provider comparison.

## Tradeoffs

Short endpointing can cut off thoughtful speakers. Two-word chunks can harm prosody or Urdu/Arabic pronunciation. Warm STT can bill silence. Tiny audio chunks add overhead/jitter. Warm resources need limits and cleanup. Every change is evaluated against latency, word retention, audio continuity, cost, and interruption together.

## What Phase 10 Means in Plain English

Phase 10 gives an agent reliable information about a business and a safe way to perform approved actions.

The **Knowledge Setup** flow lets an operator upload common files such as PDF, DOCX, TXT, Markdown, CSV, and XLSX, or enter FAQs. Wavia extracts the text in a background job, splits it into useful passages, creates local search vectors, and records where each passage came from. The operator can test questions and see the matching source before attaching the knowledge base to an agent.

During a conversation, Wavia searches only the knowledge bases attached to that exact published agent. It sends a few relevant passages to the language model as untrusted reference data, with citations. If search is slow or unavailable, the voice response continues without it instead of making the caller wait indefinitely.

Actions are different from knowledge. Knowledge helps the agent answer a question. An action changes something, such as ending a conversation or asking for a human. Phase 10 makes those two built-in actions real and sends their result back to the language model before the agent speaks. Raw computer output is never read aloud directly.

The MCP work creates a secure connection boundary for future CRM, calendar, email, inventory, payment, or other business systems. None of those systems is enabled automatically. Each future connection needs an explicit tool schema, credential reference, permission, timeout, replay protection, tests, and operator approval.

The undefined “hypercodes” term has been removed from the product roadmap. There was no code or documented behavior behind it.

Phase 10 is divided into eight checkpoints: durable knowledge records and APIs; safe file parsing; local embeddings and real vector search; fast runtime retrieval; real built-in actions; secure MCP foundations; a guided local setup screen; and final offline regression verification. The detailed plan is in [`phases/10-business-knowledge-and-safe-actions.md`](phases/10-business-knowledge-and-safe-actions.md).

## Using the Local Knowledge Setup

Start the Control Plane locally and open `http://127.0.0.1:8000/demo/`, then choose **Knowledge Setup**. Enter the local Control Plane URL and a previously issued management API key with `knowledge:read` and `knowledge:write`. Binding also requires `agent:write`. The key stays in page memory for that browser tab; Wavia clears the visible field after connecting and does not use browser storage.

The left pane tracks the eight setup steps. Create or select a knowledge base, then use the center task tabs:

1. **Upload files** accepts PDF, DOCX, TXT, Markdown, CSV, and XLSX within the displayed limits. Browser checks provide fast feedback; the server repeats authoritative MIME, signature, archive, and content validation.
2. **Add FAQ** creates one traceable question-and-answer source per submission.
3. **Test knowledge** calls the real tenant-scoped preview endpoint and shows passage text, revision, chunk, score, and citation location. If the local embedding model or database is unavailable, it reports the real error and shows no invented result.
4. **Activate & bind** enables activation only when every source in the revision is ready. Entering an agent UUID then publishes a new immutable agent configuration version with the selected knowledge revision.

The right pane polls real source status every four seconds while the tab is visible. Failed sources show their safe failure message and a retry action. Removing a source requires browser confirmation and deletes through the authenticated API. The screen never marks queued, parsing, chunking, or embedding work as ready.

FastAPI publishes the current route schemas at `http://127.0.0.1:8000/docs` and `/openapi.json`. The knowledge surface covers base creation/list/detail, source list/upload/detail/retry/delete, FAQ creation, preview query, activation, and agent binding under `/v1/knowledge-bases`.
