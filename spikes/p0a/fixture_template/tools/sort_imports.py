"""Check that import blocks are alphabetically sorted (report only)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    bad = 0
    for path in ROOT.rglob("*.py"):
        imports = [
            l for l in path.read_text(encoding="utf-8").splitlines()
            if l.startswith(("import ", "from "))
        ]
        if imports != sorted(imports):
            print(f"unsorted imports: {path.relative_to(ROOT)}")
            bad += 1
    print(f"{bad} file(s) unsorted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
