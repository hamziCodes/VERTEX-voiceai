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

    gk = (os.environ.get("PLATFORM_GLADIA_API_KEY") or os.environ.get("GLADIA_API_KEY") or "").strip()
    print(f"Gladia: key_present={bool(gk)}")
    if gk:
        # Prefer a lightweight auth probe; 401/403 = bad key, other 4xx often means key accepted.
        try:
            r = httpx.get(
                "https://api.gladia.io/v2/transcription",
                headers={"x-gladia-key": gk},
                timeout=15.0,
            )
            print(f"  Gladia ping HTTP {r.status_code} (transcription list/probe)")
        except Exception as exc:
            print(f"  Gladia ping FAIL {type(exc).__name__}: {exc}")

    groq = (os.environ.get("PLATFORM_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY") or "").strip()
    print(f"Groq: key_present={bool(groq)}")
    if groq:
        try:
            r = httpx.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {groq}"},
                timeout=15.0,
            )
            print(f"  Groq ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  Groq ping FAIL {type(exc).__name__}: {exc}")

    ck = (os.environ.get("PLATFORM_CARTESIA_API_KEY") or os.environ.get("CARTESIA_API_KEY") or "").strip()
    print(f"Cartesia: key_present={bool(ck)}")
    if ck:
        try:
            r = httpx.get(
                "https://api.cartesia.ai/voices?limit=1",
                headers={
                    "Authorization": f"Bearer {ck}",
                    "Cartesia-Version": os.environ.get("CARTESIA_VERSION", "2025-04-16"),
                },
                timeout=15.0,
            )
            print(f"  Cartesia ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  Cartesia ping FAIL {type(exc).__name__}: {exc}")

    ek = (
        os.environ.get("PLATFORM_ELEVENLABS_API_KEY")
        or os.environ.get("ELEVENLABS_API_KEY")
        or os.environ.get("ELEVEN_API_KEY")
        or ""
    ).strip()
    print(f"ElevenLabs: key_present={bool(ek)}")
    if ek:
        try:
            r = httpx.get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": ek},
                timeout=15.0,
            )
            print(f"  ElevenLabs ping HTTP {r.status_code}")
        except Exception as exc:
            print(f"  ElevenLabs ping FAIL {type(exc).__name__}: {exc}")

    uk = (os.environ.get("PLATFORM_UPLIFT_API_KEY") or os.environ.get("UPLIFT_API_KEY") or "").strip()
    print(f"Uplift: key_present={bool(uk)}")


if __name__ == "__main__":
    main()
