"""List TODO/FIXME comments."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    for path in ROOT.rglob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "TODO" in line or "FIXME" in line:
                print(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")


if __name__ == "__main__":
    main()
