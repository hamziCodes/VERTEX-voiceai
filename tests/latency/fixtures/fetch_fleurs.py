"""Fetch a tiny, pinned FLEURS subset for local latency verification.

Downloaded speech remains under ``external/`` and is intentionally ignored by Git.
The committed fetcher provides provenance; the generated local manifest records hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import urllib.parse
import urllib.request
import wave
from collections.abc import Sequence
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

DATASET_ID = "google/fleurs"
DATASET_REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
DATASET_LICENSE = "CC-BY-4.0"
DATASET_SPLIT = "validation"
CONFIGS = ("en_us", "ur_pk", "ar_eg")
_MAX_METADATA_BYTES = 2 * 1024 * 1024
_MAX_AUDIO_BYTES = 5 * 1024 * 1024


class FixtureIntegrityError(RuntimeError):
    """Raised when downloaded or existing fixture content is unsafe or unexpected."""


def _normalize_wav(content: bytes) -> bytes:
    if len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WAVE":
        raise FixtureIntegrityError("downloaded content is not a readable WAV")

    chunks: dict[bytes, bytes] = {}
    offset = 12
    while offset + 8 <= len(content):
        chunk_id = content[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", content, offset + 4)[0]
        start = offset + 8
        end = start + chunk_size
        if end > len(content):
            raise FixtureIntegrityError("downloaded content is not a readable WAV")
        chunks.setdefault(chunk_id, content[start:end])
        offset = end + (chunk_size % 2)

    fmt = chunks.get(b"fmt ")
    audio = chunks.get(b"data")
    if fmt is None or audio is None or len(fmt) < 16:
        raise FixtureIntegrityError("downloaded content is not a readable WAV")

    format_tag, channels, sample_rate, _, block_align, bits = struct.unpack_from(
        "<HHIIHH", fmt
    )
    if format_tag == 1:
        return content
    if (
        format_tag != 3
        or channels != 1
        or sample_rate != 16000
        or bits != 32
        or block_align != 4
        or len(audio) % 4
    ):
        raise FixtureIntegrityError(
            "unsupported WAV encoding; expected PCM or mono 16 kHz float32"
        )

    pcm = bytearray()
    for (value,) in struct.iter_unpack("<f", audio):
        bounded = max(-1.0, min(1.0, value))
        pcm.extend(struct.pack("<h", round(bounded * 32767)))

    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(pcm))
    return output.getvalue()


def _gender(value: object) -> str | None:
    if value in (0, "0", "male", "MALE"):
        return "male"
    if value in (1, "1", "female", "FEMALE"):
        return "female"
    return None


def select_rows(
    rows: Sequence[dict[str, Any]],
    *,
    minimum_seconds: float = 2.0,
    maximum_seconds: float = 8.0,
) -> list[dict[str, Any]]:
    """Choose short clips, preferring gender diversity when previewed."""
    by_gender: dict[str, list[dict[str, Any]]] = {"male": [], "female": []}
    usable: list[dict[str, Any]] = []
    for wrapped in rows:
        row = wrapped.get("row") or {}
        gender = _gender(row.get("gender"))
        samples = int(row.get("num_samples") or 0)
        seconds = samples / 16000.0
        audio = row.get("audio") or []
        if (
            gender in by_gender
            and minimum_seconds <= seconds <= maximum_seconds
            and isinstance(audio, list)
            and audio
            and isinstance(audio[0], dict)
            and audio[0].get("src")
        ):
            by_gender[gender].append(wrapped)
            usable.append(wrapped)

    def ordering(item: dict[str, Any]) -> tuple[int, int]:
        return int(item["row"]["num_samples"]), int(item["row_idx"])
    if by_gender["male"] and by_gender["female"]:
        return [
            min(by_gender["male"], key=ordering),
            min(by_gender["female"], key=ordering),
        ]
    if len(usable) < 2:
        raise FixtureIntegrityError(
            "fewer than two usable FLEURS preview fixtures found"
        )
    return sorted(usable, key=ordering)[:2]


def write_verified_wav(destination: Path, content: bytes) -> dict[str, object]:
    content = _normalize_wav(content)
    digest = hashlib.sha256(content).hexdigest()
    if destination.exists():
        existing_digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if existing_digest != digest:
            raise FixtureIntegrityError(
                f"existing fixture differs from downloaded audio: {destination}"
            )

    try:
        with wave.open(BytesIO(content), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()
    except (EOFError, wave.Error) as exc:
        raise FixtureIntegrityError("downloaded content is not a readable WAV") from exc

    if channels != 1 or sample_width != 2 or sample_rate != 16000:
        raise FixtureIntegrityError(
            "FLEURS fixture must be mono, PCM16, and 16 kHz; "
            f"got channels={channels}, width={sample_width}, rate={sample_rate}"
        )

    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    return {
        "sha256": digest,
        "bytes": len(content),
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "duration_ms": frames * 1000.0 / sample_rate,
    }


def _read_url(url: str, *, maximum_bytes: int) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "wavia-latency-fixtures/1"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        declared = int(response.headers.get("Content-Length") or 0)
        if declared > maximum_bytes:
            raise FixtureIntegrityError(
                f"download exceeds {maximum_bytes} byte safety limit"
            )
        content = response.read(maximum_bytes + 1)
    if len(content) > maximum_bytes:
        raise FixtureIntegrityError(
            f"download exceeds {maximum_bytes} byte safety limit"
        )
    return content


def _verify_current_revision() -> None:
    metadata = json.loads(
        _read_url(
            f"https://huggingface.co/api/datasets/{DATASET_ID}",
            maximum_bytes=_MAX_METADATA_BYTES,
        )
    )
    actual = metadata.get("sha")
    if actual != DATASET_REVISION:
        raise FixtureIntegrityError(
            "FLEURS revision changed; review the dataset before updating the pin"
        )


def _preview_rows(config: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {"dataset": DATASET_ID, "config": config, "split": DATASET_SPLIT}
    )
    payload = json.loads(
        _read_url(
            f"https://datasets-server.huggingface.co/first-rows?{query}",
            maximum_bytes=_MAX_METADATA_BYTES,
        )
    )
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise FixtureIntegrityError(f"FLEURS preview returned no rows for {config}")
    return rows


def _validated_audio_url(row: dict[str, Any]) -> str:
    source = str(row["row"]["audio"][0]["src"])
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme != "https" or parsed.hostname != "datasets-server.huggingface.co":
        raise FixtureIntegrityError("unexpected FLEURS audio source host")
    return source


def fetch_subset(output_dir: Path) -> Path:
    _verify_current_revision()
    records: list[dict[str, object]] = []
    for config in CONFIGS:
        for wrapped in select_rows(_preview_rows(config)):
            row = wrapped["row"]
            row_index = int(wrapped["row_idx"])
            gender = _gender(row.get("gender"))
            content = _read_url(
                _validated_audio_url(wrapped), maximum_bytes=_MAX_AUDIO_BYTES
            )
            relative = Path(config) / f"validation-{row_index}-{gender}.wav"
            audio_metadata = write_verified_wav(output_dir / relative, content)
            records.append(
                {
                    "config": config,
                    "split": DATASET_SPLIT,
                    "row_index": row_index,
                    "dataset_id": int(row["id"]),
                    "gender": gender,
                    "transcription": str(row["transcription"]),
                    "path": relative.as_posix(),
                    **audio_metadata,
                }
            )

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": DATASET_ID,
        "revision": DATASET_REVISION,
        "license": DATASET_LICENSE,
        "source": "https://huggingface.co/datasets/google/fleurs",
        "paper": "https://arxiv.org/abs/2205.12446",
        "files": records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "external" / "fleurs",
    )
    parser.add_argument(
        "--accept-license",
        action="store_true",
        help="Confirm use of the FLEURS CC BY 4.0 fixtures.",
    )
    args = parser.parse_args()
    if not args.accept_license:
        parser.error("--accept-license is required (FLEURS is CC BY 4.0)")
    manifest = fetch_subset(args.output_dir)
    print(f"prepared FLEURS fixtures: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
