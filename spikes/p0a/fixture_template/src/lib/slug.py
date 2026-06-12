import re

_NON_WORD = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _NON_WORD.sub("-", text.lower()).strip("-")


def unique_slug(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"
