"""Strip trailing whitespace from tracked python files."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    changed = 0
    for path in ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        cleaned = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
        if cleaned != text:
            path.write_text(cleaned, encoding="utf-8")
            changed += 1
    print(f"cleaned {changed} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
