def points_for_amount(amount_cents: int) -> int:
    return amount_cents // 500


def tier_for_points(points: int) -> str:
    if points >= 1000:
        return "platinum"
    if points >= 400:
        return "gold"
    if points >= 100:
        return "silver"
    return "bronze"
