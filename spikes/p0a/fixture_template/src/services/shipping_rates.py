_BASE_CENTS = {"dhl": 499, "ups": 549, "fedex": 599}


def rate_for(carrier: str, weight_kg: float) -> int:
    base = _BASE_CENTS.get(carrier, 650)
    return base + round(weight_kg * 120)
