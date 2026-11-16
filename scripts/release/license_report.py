"""Print the license of every installed distribution, as JSON lines.

Reads PEP 639 ``License-Expression`` first, then the ``License`` field, then
trove classifiers. Run it inside a built image to cover exactly what ships::

    docker run --rm -i wavia-control-plane:p15 python - < scripts/release/license_report.py

Exit status 1 lists any distribution whose license is unknown or is not on
the permissive allow-list, so a reviewer looks at it before release.
"""

from __future__ import annotations

import json
import re
import sys
from importlib import metadata

ALLOWED = re.compile(
    r"\b(MIT|BSD|Apache|ISC|PSF|Python Software Foundation|MPL|Mozilla Public"
    r"|Unlicense|0BSD|Zlib|HPND)\b",
    re.IGNORECASE,
)
# pip/setuptools/wheel come with the base Python image, not from the lock.
TOOLING = {"pip", "setuptools", "wheel"}


def license_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression.strip()
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::") and "OSI Approved" != c.split("::")[-1].strip()
    ]
    if classifiers:
        return " / ".join(classifiers)
    text = (meta.get("License") or "").strip()
    first = text.splitlines()[0] if text else ""
    return first[:80] or "UNKNOWN"


def main() -> int:
    review = []
    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        license_name = license_of(dist)
        ok = name.lower() in TOOLING or bool(ALLOWED.search(license_name))
        print(json.dumps({"name": name, "version": dist.version, "license": license_name, "ok": ok}))
        if not ok:
            review.append(f"{name} {dist.version}: {license_name}")
    if review:
        print("REVIEW:\n  " + "\n  ".join(review), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
