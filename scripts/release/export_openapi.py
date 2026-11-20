"""Write (or, with --check, verify) ``openapi.yaml`` from the running app.

The control plane's own FastAPI schema is the contract; ``openapi.yaml`` is a
published copy of it for SDK authors and reviewers, never a hand-edited spec.

    python scripts/release/export_openapi.py          # rewrite openapi.yaml
    python scripts/release/export_openapi.py --check  # exit 1 if it drifted
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "openapi.yaml"
HEADER = (
    "# GENERATED from control_plane.app by scripts/release/export_openapi.py.\n"
    "# Do not edit by hand; CI-style check: --check.\n"
)


def runtime_schema() -> dict[str, Any]:
    os.environ.setdefault("UCVE_ENV", "test")
    sys.path.insert(0, str(REPO_ROOT))
    from control_plane.app import app

    return app.openapi()


def render(schema: dict[str, Any]) -> str:
    import yaml

    body = yaml.safe_dump(schema, sort_keys=False, allow_unicode=True, width=100)
    return HEADER + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render(runtime_schema())
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
        if current != text:
            print("openapi.yaml differs from the runtime schema; regenerate it.", file=sys.stderr)
            return 1
        print("openapi.yaml matches the runtime schema")
        return 0
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {TARGET.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
