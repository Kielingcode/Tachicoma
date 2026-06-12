import hashlib


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def is_internal(token: str) -> bool:
    return token.startswith("int-")
