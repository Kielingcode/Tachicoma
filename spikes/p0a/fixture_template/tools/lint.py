"""Report lines longer than 100 chars across the project."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    bad = 0
    for path in ROOT.rglob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if len(line) > 100:
                print(f"{path.relative_to(ROOT)}:{i}: line too long ({len(line)})")
                bad += 1
    print(f"{bad} issue(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
