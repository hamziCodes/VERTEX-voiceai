"""Ping UCVE provider APIs using .env keys (never prints secrets)."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    print("RUN_LIVE_PROVIDERS=", os.environ.get("RUN_LIVE_PROVIDERS"))
    print("UCVE_PIPELINE_V2=", os.environ.get("UCVE_PIPELINE_V2"))

    # STT: Gladia
    gk = (os.environ.get("PLATFORM_GLADIA_API_KEY") or os.environ.get("GLADIA_API_KEY") or "").strip()
    print(f"Gladia STT: key_present={bool(gk)}")
    if gk:
        try:
            r = httpx.get(
                "https://api.gladia.io/v2/transcription",
                headers={"x-gladia-key": gk},
                timeout=10.0,
            )
            print(f"  Gladia ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  Gladia ping FAIL: {exc}")

    # STT: Deepgram
    dgk = (os.environ.get("PLATFORM_DEEPGRAM_API_KEY") or os.environ.get("DEEPGRAM_API_KEY") or "").strip()
    print(f"Deepgram STT: key_present={bool(dgk)}")
    if dgk:
        try:
            r = httpx.get(
                "https://api.deepgram.com/v1/projects",
                headers={"Authorization": f"Token {dgk}"},
                timeout=10.0,
            )
            print(f"  Deepgram ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  Deepgram ping FAIL: {exc}")

    # LLM: Groq
    groq = (os.environ.get("PLATFORM_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY") or "").strip()
    print(f"Groq LLM: key_present={bool(groq)}")
    if groq:
        try:
            r = httpx.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {groq}"},
                timeout=10.0,
            )
            print(f"  Groq ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  Groq ping FAIL: {exc}")

    # LLM: Google Gemini
    gemini = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    print(f"Google Gemini LLM: key_present={bool(gemini)}")
    if gemini:
        try:
            # Header, not ?key=: a query-string key lands in proxy logs and in
            # httpx error messages, which this script prints.
            r = httpx.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                headers={"x-goog-api-key": gemini},
                timeout=10.0,
            )
            print(f"  Gemini ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  Gemini ping FAIL: {exc}")

    # LLM: OpenAI
    openai_k = (os.environ.get("PLATFORM_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    print(f"OpenAI LLM: key_present={bool(openai_k)}")
    if openai_k:
        try:
            r = httpx.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {openai_k}"},
                timeout=10.0,
            )
            print(f"  OpenAI ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  OpenAI ping FAIL: {exc}")

    # TTS: Cartesia
    ck = (os.environ.get("PLATFORM_CARTESIA_API_KEY") or os.environ.get("CARTESIA_API_KEY") or "").strip()
    print(f"Cartesia TTS: key_present={bool(ck)}")
    if ck:
        try:
            r = httpx.get(
                "https://api.cartesia.ai/voices?limit=1",
                headers={
                    "Authorization": f"Bearer {ck}",
                    "Cartesia-Version": os.environ.get("CARTESIA_VERSION", "2025-04-16"),
                },
                timeout=10.0,
            )
            print(f"  Cartesia ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  Cartesia ping FAIL: {exc}")

    # TTS: ElevenLabs
    ek = (
        os.environ.get("PLATFORM_ELEVENLABS_API_KEY")
        or os.environ.get("ELEVENLABS_API_KEY")
        or os.environ.get("ELEVEN_API_KEY")
        or ""
    ).strip()
    print(f"ElevenLabs TTS: key_present={bool(ek)}")
    if ek:
        try:
            r = httpx.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": ek},
                timeout=10.0,
            )
            print(f"  ElevenLabs ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  ElevenLabs ping FAIL: {exc}")

    # TTS: Uplift
    uk = (os.environ.get("PLATFORM_UPLIFT_API_KEY") or os.environ.get("UPLIFT_API_KEY") or "").strip()
    print(f"Uplift TTS: key_present={bool(uk)}")

    # Telephony: Telnyx
    tk = (os.environ.get("TELNYX_API_KEY") or "").strip()
    print(f"Telnyx Telephony: key_present={bool(tk)}")
    if tk:
        try:
            r = httpx.get(
                "https://api.telnyx.com/v2/phone_numbers",
                headers={"Authorization": f"Bearer {tk}"},
                timeout=10.0,
            )
            print(f"  Telnyx ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  Telnyx ping FAIL: {exc}")


if __name__ == "__main__":
    main()
