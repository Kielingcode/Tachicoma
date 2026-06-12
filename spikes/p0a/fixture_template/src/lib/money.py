def cents_to_display(cents: int, symbol: str = "$") -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{symbol}{cents // 100}.{cents % 100:02d}"


def apply_percentage(cents: int, pct: float) -> int:
    return round(cents * pct / 100.0)


def split_even(total_cents: int, parts: int) -> list[int]:
    base = total_cents // parts
    remainder = total_cents - base * parts
    return [base + (1 if i < remainder else 0) for i in range(parts)]
