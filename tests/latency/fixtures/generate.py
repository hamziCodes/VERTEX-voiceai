"""Generate PCM16 fixtures from the checked-in latency manifest."""

from __future__ import annotations

import hashlib
import math
import random
import struct
from collections.abc import Mapping


def generate_case_pcm(case: Mapping[str, object]) -> bytes:
    sample_rate = int(case["sample_rate"])
    duration_ms = int(case["duration_ms"])
    sample_count = int(sample_rate * duration_ms / 1000)
    pattern = str(case["generator"])
    case_id = str(case["id"])

    if pattern == "silence":
        samples = [0] * sample_count
    elif pattern == "low-amplitude-tone":
        samples = [
            int(250 * math.sin(2 * math.pi * 220.0 * index / sample_rate))
            for index in range(sample_count)
        ]
    elif pattern == "seeded-noise":
        seed = int.from_bytes(
            hashlib.sha256(case_id.encode("utf-8")).digest()[:8], "big"
        )
        rng = random.Random(seed)
        samples = [rng.randint(-500, 500) for _ in range(sample_count)]
    elif pattern == "segmented-silence":
        samples = []
        for index in range(sample_count):
            segment = (index * 1000 // sample_rate) // 250
            if segment % 2 == 0:
                value = int(1000 * math.sin(2 * math.pi * 180.0 * index / sample_rate))
            else:
                value = 0
            samples.append(value)
    else:
        raise ValueError(f"unsupported synthetic fixture generator: {pattern}")

    return b"".join(struct.pack("<h", sample) for sample in samples)
