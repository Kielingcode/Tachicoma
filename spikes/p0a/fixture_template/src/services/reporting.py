from collections import Counter


def top_carriers(carrier_events: list[str], n: int = 3) -> list[str]:
    counts = Counter(carrier_events)
    return [carrier for carrier, _ in counts.most_common(n)]


def revenue_by_key(rows: list[tuple[str, int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, cents in rows:
        out[key] = out.get(key, 0) + cents
    return out
