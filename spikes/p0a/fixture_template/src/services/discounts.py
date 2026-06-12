_TIER_DISCOUNT_PCT = {"bronze": 0, "silver": 3, "gold": 7, "platinum": 12}


def discount_pct_for_tier(tier: str) -> int:
    return _TIER_DISCOUNT_PCT.get(tier, 0)


def apply_discount(amount_cents: int, pct: int) -> int:
    return amount_cents - (amount_cents * pct) // 100
