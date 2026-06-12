"""Verify every package directory has an __init__.py."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    missing = []
    for pkg in ("src", "src/lib", "src/services", "src/api", "tests"):
        if not (ROOT / pkg / "__init__.py").exists():
            missing.append(pkg)
    if missing:
        print("missing __init__.py in: " + ", ".join(missing))
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
