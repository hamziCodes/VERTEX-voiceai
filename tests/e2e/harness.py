"""End-to-end validation harness (Phase 33 / Remediation R0).

Orchestrates mock provider stack or optional docker compose lifecycle,
runs scenario modules, and asserts phase exit criteria.

Usage:
    python -m tests.e2e.harness --scenario sovereign_conversation
    pytest tests/e2e/ -v

CI: mock providers on every PR; compose-backed nightly job [LATER].
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

ScenarioFn = Callable[["HarnessConfig"], Any]


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


@dataclass
class ScenarioResult:
    """Outcome of a single harness scenario."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, **metrics: Any) -> ScenarioResult:
        return cls(passed=True, metrics=dict(metrics))

    @classmethod
    def fail(cls, *failures: str, **metrics: Any) -> ScenarioResult:
        return cls(passed=False, failures=list(failures), metrics=dict(metrics))


_SCENARIO_REGISTRY: dict[str, ScenarioFn] = {}


def _get_registry() -> dict[str, ScenarioFn]:
    """Ensure __main__ and tests.e2e.harness share the same scenario registry instance."""
    mod = sys.modules.get("tests.e2e.harness")
    if mod is not None and hasattr(mod, "_SCENARIO_REGISTRY"):
        return mod._SCENARIO_REGISTRY
    return _SCENARIO_REGISTRY


def register_scenario(name: str) -> Callable[[ScenarioFn], ScenarioFn]:
    """Decorator to register a scenario runner by name."""

    def _wrap(fn: ScenarioFn) -> ScenarioFn:
        _get_registry()[name] = fn
        _SCENARIO_REGISTRY[name] = fn
        return fn

    return _wrap


def get_scenario(name: str) -> ScenarioFn:
    registry = _get_registry()
    if name not in registry:
        # Lazy-import built-in scenarios so registry populates on first use.
        from tests.e2e.scenarios import sovereign_conversation as _sovereign  # noqa: F401

        _ = _sovereign
        registry = _get_registry()
    if name not in registry:
        raise KeyError(f"Unknown scenario: {name!r}. Known: {sorted(registry)}")
    return registry[name]


def list_scenarios() -> list[str]:
    try:
        get_scenario("sovereign_conversation")
    except KeyError:
        pass
    return sorted(_get_registry())


class E2EHarness:
    """Dispatches named scenarios against mock or compose stacks."""

    def __init__(self, config: HarnessConfig | None = None) -> None:
        self.config = config or HarnessConfig()

    def up(self) -> None:
        """Start mock stack or compose services."""
        if self.config.mode is HarnessMode.COMPOSE:
            # Optional: docker compose lifecycle fixture [LATER]
            pass

    def down(self) -> None:
        """Tear down resources."""
        pass

    def run(self) -> bool:
        """Execute configured scenario; return success (False on any failure)."""
        self.up()
        try:
            result = self.run_scenario(self.config.scenario)
            return result.passed
        finally:
            self.down()

    def run_scenario(self, name: str) -> ScenarioResult:
        """Dispatch a named scenario and normalize sync/async runners."""
        inject = self.config.extra.get("inject_failure")
        if inject is True or inject == name:
            return ScenarioResult.fail(f"injected failure for scenario {name!r}")

        fn = get_scenario(name)
        outcome = fn(self.config)
        if asyncio.iscoroutine(outcome):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # Nested event loop: scenario should be awaited by caller via run_scenario_async.
                raise RuntimeError(
                    "async scenario invoked from sync run() inside a running loop; "
                    "use await harness.run_scenario_async(name)"
                )
            result = asyncio.run(outcome)
        else:
            result = outcome
        if not isinstance(result, ScenarioResult) and type(result).__name__ != "ScenarioResult":
            return ScenarioResult.fail(f"scenario {name!r} returned non-ScenarioResult")
        return result

    async def run_scenario_async(self, name: str) -> ScenarioResult:
        inject = self.config.extra.get("inject_failure")
        if inject is True or inject == name:
            return ScenarioResult.fail(f"injected failure for scenario {name!r}")

        fn = get_scenario(name)
        outcome = fn(self.config)
        if asyncio.iscoroutine(outcome):
            result = await outcome
        else:
            result = outcome
        if not isinstance(result, ScenarioResult) and type(result).__name__ != "ScenarioResult":
            return ScenarioResult.fail(f"scenario {name!r} returned non-ScenarioResult")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="UCVE E2E harness")
    parser.add_argument("--scenario", default="sovereign_conversation")
    parser.add_argument("--compose", action="store_true")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered scenarios and exit",
    )
    args = parser.parse_args()
    if args.list:
        for name in list_scenarios():
            print(name)
        return 0
    mode = HarnessMode.COMPOSE if args.compose else HarnessMode.MOCK
    harness = E2EHarness(HarnessConfig(mode=mode, scenario=args.scenario))
    res = harness.run_scenario(args.scenario)
    if res.passed:
        print(f"Scenario '{args.scenario}' PASSED: {res.metrics}")
        return 0
    print(f"Scenario '{args.scenario}' FAILED: {res.failures}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
