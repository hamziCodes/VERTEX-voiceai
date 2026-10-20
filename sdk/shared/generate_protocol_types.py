"""Generate lightweight Python and TypeScript wire types from event_schema.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "sdk" / "shared" / "event_schema.json"
PYTHON_PATH = ROOT / "sdk" / "python" / "ucve" / "protocol_generated.py"
TYPESCRIPT_PATH = ROOT / "sdk" / "typescript" / "src" / "protocol.generated.ts"


def _event_names(schema: dict[str, Any]) -> list[str]:
    return [item["properties"]["event_type"]["const"] for item in schema["oneOf"]]


def render_python(schema: dict[str, Any]) -> str:
    events = "\n".join(f'    "{name}",' for name in _event_names(schema))
    version = schema["protocol_version"]
    supported = schema["supported_range"]
    return f'''"""Generated from sdk/shared/event_schema.json. Do not edit."""

from __future__ import annotations

from typing import Any, Final, Literal, TypedDict

PROTOCOL_VERSION: Final = "{version}"
SUPPORTED_PROTOCOL_RANGE: Final = "{supported}"

RealtimeEventType = Literal[
{events}
]


class RealtimeEvent(TypedDict):
    protocol_version: str
    event_id: str
    sequence: int
    event_type: RealtimeEventType
    timestamp_ms: float
    payload: dict[str, Any]
'''


def render_typescript(schema: dict[str, Any]) -> str:
    events = "\n".join(f"  | '{name}'" for name in _event_names(schema))
    version = schema["protocol_version"]
    supported = schema["supported_range"]
    return f"""/** Generated from sdk/shared/event_schema.json. Do not edit. */

export const PROTOCOL_VERSION = '{version}' as const;
export const SUPPORTED_PROTOCOL_RANGE = '{supported}' as const;

export type RealtimeEventType =
{events};

export interface RealtimeEvent<
  T extends Record<string, unknown> = Record<string, unknown>
> {{
  protocol_version: typeof PROTOCOL_VERSION;
  event_id: string;
  sequence: number;
  event_type: RealtimeEventType;
  timestamp_ms: number;
  payload: T;
}}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    schema = json.loads(SCHEMA_PATH.read_text("utf-8"))
    outputs = {
        PYTHON_PATH: render_python(schema),
        TYPESCRIPT_PATH: render_typescript(schema),
    }
    if args.check:
        matches = all(
            path.read_text("utf-8") == text for path, text in outputs.items()
        )
        return 0 if matches else 1
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
