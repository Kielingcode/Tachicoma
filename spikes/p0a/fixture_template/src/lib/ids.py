import string

_ALPHABET = string.ascii_lowercase + string.digits


def is_valid_id(value: str, prefix: str) -> bool:
    if not value.startswith(prefix + "-"):
        return False
    body = value[len(prefix) + 1 :]
    return bool(body) and all(c in _ALPHABET for c in body)


def normalize_id(value: str) -> str:
    return value.strip().lower().replace("_", "-")
