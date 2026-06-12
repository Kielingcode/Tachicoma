"""Time the import of each src module."""

import importlib
import time

MODULES = [
    "src.lib.strutil", "src.lib.dates", "src.lib.money", "src.lib.ids",
    "src.lib.validation", "src.lib.pagination", "src.lib.slug", "src.lib.retry",
    "src.services.pricing", "src.services.tax", "src.api.handlers",
]


def main() -> None:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    for mod in MODULES:
        t0 = time.perf_counter()
        importlib.import_module(mod)
        print(f"{mod:28} {(time.perf_counter() - t0) * 1000:.2f} ms")


if __name__ == "__main__":
    main()
