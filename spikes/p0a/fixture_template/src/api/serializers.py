from src.lib.money import cents_to_display


def order_summary(order_id: str, amount_cents: int) -> dict:
    return {"id": order_id, "display_total": cents_to_display(amount_cents)}


def customer_summary(name: str, tier: str) -> dict:
    return {"name": name, "badge": tier.upper()}
