# FLEURS fixture policy

The optional real-speech latency corpus uses a tiny subset of `google/fleurs`:

- pinned revision: `70bb2e84b976b7e960aa89f1c648e09c59f894dd`;
- configurations: `en_us`, `ur_pk`, and `ar_eg`;
- split: validation;
- selection: two shortest 2–8 second clips exposed by the preview, preferring one male and one female where both appear;
- license: Creative Commons Attribution 4.0;
- upstream dataset: <https://huggingface.co/datasets/google/fleurs>;
- paper: <https://arxiv.org/abs/2205.12446>.

The six downloaded WAV files and their generated manifest stay under the ignored `external/fleurs/` directory. They are not committed or redistributed by this repository. The generated manifest records the exact upstream revision, row, transcript, audio properties, and SHA-256 hash.

From the repository root:

```powershell
py -3.12 -m tests.latency.fixtures.fetch_fleurs --accept-license
```

This is a free dataset download. It does not call an STT, LLM, TTS, or telephony provider. The downloader refuses a changed upstream revision, non-Hugging-Face audio host, oversized response, invalid WAV, unexpected audio format, or a local file whose hash differs.

FLEURS supplies read speech and does not cover natural Urdu/English code switching. Use the already committed legacy `minglish_test.wav` for pipeline timing only until Hamzi supplies or records a short non-sensitive code-switched acceptance clip with a known transcript.
