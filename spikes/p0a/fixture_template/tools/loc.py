"""Count non-blank lines of python per top-level package."""

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    counts: Counter[str] = Counter()
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        top = rel.parts[0]
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        counts[top] += len(lines)
    for pkg, n in counts.most_common():
        print(f"{pkg:12} {n}")


if __name__ == "__main__":
    main()
