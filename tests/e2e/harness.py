"""End-to-end validation harness (Phase 33).

Orchestrates mock provider stack or optional docker compose lifecycle,
runs scenario modules, and asserts phase exit criteria.

Usage:
    python -m tests.e2e.harness --scenario sovereign_conversation
    pytest tests/e2e/scenarios/ -v

CI: mock providers on every PR; compose-backed nightly job [LATER].
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HarnessMode(str, Enum):
    MOCK = "mock"
    COMPOSE = "compose"


@dataclass
class HarnessConfig:
    mode: HarnessMode = HarnessMode.MOCK
    control_plane_url: str = "http://localhost:8080"
    worker_ws_url: str = "ws://localhost:8081/ws"
    scenario: str = "sovereign_conversation"
    extra: dict[str, Any] = field(default_factory=dict)


class E2EHarness:
    """Minimal stub — wires scenario name to future scenario runners."""

    def __init__(self, config: HarnessConfig | None = None) -> None:
        self.config = config or HarnessConfig()

    def up(self) -> None:
        """Start mock stack or compose services."""
        if self.config.mode is HarnessMode.COMPOSE:
            # Optional: docker compose lifecycle fixture
            pass

    def down(self) -> None:
        """Tear down resources."""
        pass

    def run(self) -> bool:
        """Execute configured scenario; return success."""
        self.up()
        try:
            # Scenario dispatch placeholder
            return True
        finally:
            self.down()


def main() -> int:
    parser = argparse.ArgumentParser(description="UCVE E2E harness")
    parser.add_argument("--scenario", default="sovereign_conversation")
    parser.add_argument("--compose", action="store_true")
    args = parser.parse_args()
    mode = HarnessMode.COMPOSE if args.compose else HarnessMode.MOCK
    harness = E2EHarness(HarnessConfig(mode=mode, scenario=args.scenario))
    return 0 if harness.run() else 1


if __name__ == "__main__":
    raise SystemExit(main())
