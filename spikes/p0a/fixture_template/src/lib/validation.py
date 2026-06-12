import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value))


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def require_keys(d: dict, keys: list[str]) -> list[str]:
    return [k for k in keys if k not in d]
