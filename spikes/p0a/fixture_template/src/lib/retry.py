def backoff_schedule(attempts: int, base_ms: int = 100, cap_ms: int = 5000) -> list[int]:
    out = []
    delay = base_ms
    for _ in range(attempts):
        out.append(min(delay, cap_ms))
        delay *= 2
    return out
