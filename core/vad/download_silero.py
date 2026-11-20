"""Fetch the pinned Silero VAD ONNX model into ``core/vad/models/``.

The model is not committed (binary, MIT-licensed upstream). This script pins
the exact release and verifies its SHA-256, so every checkout, image and test
machine runs the same model. A file that is present but has another hash is
replaced; a download whose hash differs is rejected and not written.

Usage (from the repository root)::

    python -m core.vad.download_silero          # fetch if missing or wrong
    python -m core.vad.download_silero --check  # verify only (exit 1 if bad)
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
import urllib.request
from pathlib import Path

SILERO_VERSION = "v6.2.1"
SILERO_SHA256 = "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"
SILERO_BYTES = 2_327_524
_MODEL_URL = (
    "https://github.com/snakers4/silero-vad/raw/"
    f"{SILERO_VERSION}/src/silero_vad/data/silero_vad.onnx"
)
_DEST = Path(__file__).resolve().parent / "models" / "silero_vad.onnx"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_valid(path: Path = _DEST) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == SILERO_BYTES
        and _sha256(path) == SILERO_SHA256
    )


def fetch(dest: Path = _DEST) -> Path:
    if is_valid(dest):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        with urllib.request.urlopen(_MODEL_URL, timeout=60) as response:  # noqa: S310
            temporary.write_bytes(response.read(SILERO_BYTES + 1))
        if not is_valid(temporary):
            raise SystemExit(
                f"Downloaded Silero model does not match {SILERO_VERSION} "
                f"sha256 {SILERO_SHA256}; refusing to install it."
            )
        temporary.replace(dest)
    finally:
        temporary.unlink(missing_ok=True)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only")
    args = parser.parse_args()
    if args.check:
        ok = is_valid()
        print(f"Silero {SILERO_VERSION}: {'ok' if ok else 'missing or wrong hash'}")
        sys.exit(0 if ok else 1)
    path = fetch()
    print(f"Silero {SILERO_VERSION} verified at {path}")


if __name__ == "__main__":
    main()
