"""Fetch the pinned local embedding bundle (intfloat/multilingual-e5-small).

The bundle is not committed (large binary, MIT-licensed upstream). This script
pins the exact upstream revision and every file's size and SHA-256, so each
image and machine runs the same model; a file whose hash differs is never
installed. It writes the ``embedding_model.json`` metadata that
``LocalONNXEmbedder`` requires (see ``MODEL_BUNDLE.md``).

    python -m core.rag.embedders.download_model --dest /opt/wavia/models/multilingual-e5-small
    python -m core.rag.embedders.download_model --dest DIR --check   # verify only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

MODEL_ID = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
LICENSE = "MIT"
_BASE = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/"

# local name -> (upstream path, bytes, sha256)
FILES: dict[str, tuple[str, int, str]] = {
    "model.onnx": (
        "onnx/model.onnx",
        470_268_510,
        "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665",
    ),
    "tokenizer.json": (
        "onnx/tokenizer.json",
        17_082_730,
        "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
    ),
}

METADATA = {
    "model_id": MODEL_ID,
    "version": REVISION,
    "dimensions": 384,
    "max_length": 512,
    "query_prefix": "query: ",
    "passage_prefix": "passage: ",
    "pad_id": 1,
    "pad_token": "<pad>",
    "license": LICENSE,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _valid(path: Path, size: int, sha256: str) -> bool:
    return path.is_file() and path.stat().st_size == size and _sha256(path) == sha256


def bundle_is_valid(dest: Path) -> bool:
    metadata = dest / "embedding_model.json"
    if not metadata.is_file():
        return False
    try:
        if json.loads(metadata.read_text(encoding="utf-8")) != METADATA:
            return False
    except json.JSONDecodeError:
        return False
    return all(_valid(dest / name, size, sha) for name, (_, size, sha) in FILES.items())


def _download(upstream: str, target: Path, size: int, sha256: str) -> None:
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        digest = hashlib.sha256()
        written = 0
        with urllib.request.urlopen(_BASE + upstream, timeout=120) as response:  # noqa: S310
            with temporary.open("wb") as out:
                while chunk := response.read(1 << 20):
                    written += len(chunk)
                    if written > size:
                        raise SystemExit(f"{upstream}: larger than the pinned size; refusing it.")
                    digest.update(chunk)
                    out.write(chunk)
        if written != size or digest.hexdigest() != sha256:
            raise SystemExit(
                f"{upstream}: size or SHA-256 does not match revision {REVISION}; refusing it."
            )
        # NamedTemporaryFile creates files 0600; the services run as a
        # non-root user, so the bundle must be world-readable.
        temporary.chmod(0o644)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def fetch(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for name, (upstream, size, sha256) in FILES.items():
        target = dest / name
        if not _valid(target, size, sha256):
            _download(upstream, target, size, sha256)
    (dest / "embedding_model.json").write_text(
        json.dumps(METADATA, indent=2) + "\n", encoding="utf-8"
    )
    for path in (dest, *dest.iterdir()):
        path.chmod(0o755 if path.is_dir() else 0o644)
    if not bundle_is_valid(dest):
        raise SystemExit("Embedding bundle failed verification after download.")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument("--check", action="store_true", help="verify only")
    args = parser.parse_args()
    if args.check:
        ok = bundle_is_valid(args.dest)
        print(f"{MODEL_ID}@{REVISION[:8]}: {'ok' if ok else 'missing or wrong hash'}")
        sys.exit(0 if ok else 1)
    fetch(args.dest)
    print(f"{MODEL_ID}@{REVISION[:8]} verified at {args.dest}")


if __name__ == "__main__":
    main()
