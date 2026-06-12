def truncate(s: str, limit: int, suffix: str = "...") -> str:
    if len(s) <= limit:
        return s
    return s[: max(0, limit - len(suffix))] + suffix


def collapse_ws(s: str) -> str:
    return " ".join(s.split())


def initials(name: str) -> str:
    return "".join(part[0].upper() for part in name.split() if part)
