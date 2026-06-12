"""Naive dead-code scan: top-level functions never referenced elsewhere."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    defined: dict[str, Path] = {}
    bodies: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        bodies.append(text)
        for node in ast.parse(text).body:
            if isinstance(node, ast.FunctionDef):
                defined[node.name] = path
    blob = "\n".join(bodies) + "\n".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "tests").rglob("*.py")
    )
    for name, path in sorted(defined.items()):
        if blob.count(name) <= 1:
            print(f"possibly dead: {name} ({path.relative_to(ROOT)})")


if __name__ == "__main__":
    main()
