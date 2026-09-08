"""Download Silero VAD ONNX into ``core/vad/models/silero_vad.onnx``.

Usage (from repo root)::

    python -m core.vad.download_silero
"""

from __future__ import annotations

from pathlib import Path

_MODEL_URL = (
    "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
)
_DEST = Path(__file__).resolve().parent / "models" / "silero_vad.onnx"


def main() -> None:
    import urllib.request

    _DEST.parent.mkdir(parents=True, exist_ok=True)
    if _DEST.is_file() and _DEST.stat().st_size > 1000:
        print(f"Silero ONNX already present: {_DEST}")
        return
    print(f"Downloading Silero VAD ONNX -> {_DEST}")
    urllib.request.urlretrieve(_MODEL_URL, _DEST)
    print(f"Wrote {_DEST} ({_DEST.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
