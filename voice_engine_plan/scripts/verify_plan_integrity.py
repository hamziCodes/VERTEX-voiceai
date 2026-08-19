#!/usr/bin/env python3
"""Verify voice_engine_plan/ integrity — phases, tests, trackers."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_ROOT = REPO_ROOT / "voice_engine_plan"
PLAN_DIR = PLAN_ROOT / "implementation_plan"
TEST_DIR = PLAN_ROOT / "tests" / "phase_tests"
TRACKER = PLAN_DIR / "EXECUTION_TRACKER.md"
TEST_TRACKER = TEST_DIR / "TEST_TRACKER.md"

EXPECTED_PHASES = 36


def main() -> int:
    errors: list[str] = []

    phase_files = sorted(PLAN_DIR.glob("phase_*.md"))
    if len(phase_files) != EXPECTED_PHASES:
        errors.append(f"Expected {EXPECTED_PHASES} phase files, found {len(phase_files)}")

    for pf in phase_files:
        text = pf.read_text(encoding="utf-8")
        if "## 6. Ambiguity Flags" not in text:
            errors.append(f"{pf.name}: missing §6")
        if "## 7. Test Spec" not in text:
            errors.append(f"{pf.name}: missing §7")
        if "Human Decision Points" in text and "? —" in text:
            errors.append(f"{pf.name}: open ambiguity question mark found")

    for i in range(EXPECTED_PHASES):
        test_name = f"test_phase_{i:02d}_"
        matches = list(TEST_DIR.glob(f"{test_name}*.py"))
        if not matches:
            errors.append(f"Missing test file for phase {i:02d}")

    if TRACKER.is_file():
        rows = [
            line
            for line in TRACKER.read_text(encoding="utf-8").splitlines()
            if re.match(r"^\| \d{2} \|", line)
        ]
        if len(rows) != EXPECTED_PHASES:
            errors.append(f"EXECUTION_TRACKER: expected {EXPECTED_PHASES} rows, found {len(rows)}")
    else:
        errors.append("EXECUTION_TRACKER.md missing")

    if not (PLAN_ROOT / "README.md").is_file():
        errors.append("voice_engine_plan/README.md missing")

    if errors:
        print("PLAN INTEGRITY FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: {EXPECTED_PHASES} phases, tests, and trackers verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
