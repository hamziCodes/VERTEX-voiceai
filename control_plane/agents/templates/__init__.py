"""UCVE Agent Builder - Platform Seed Templates Package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).resolve().parent


def load_template(name: str) -> dict[str, Any]:
    """Load a platform starter template by name (e.g. 'retail_customer_service', 'clinic_intake')."""
    path = TEMPLATES_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Template '{name}' not found in {TEMPLATES_DIR}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_templates() -> list[str]:
    """Return available platform seed template identifiers."""
    return [p.stem for p in TEMPLATES_DIR.glob("*.json")]
