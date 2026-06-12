"""Bump the project version stored in VERSION."""

import sys
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def main(part: str = "patch") -> None:
    raw = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "0.1.0"
    major, minor, patch = (int(x) for x in raw.split("."))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    VERSION_FILE.write_text(f"{major}.{minor}.{patch}\n")
    print(f"{raw} -> {major}.{minor}.{patch}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "patch")
