from src.lib.money import apply_percentage
from src.models import Order


def order_total_with_fee(order: Order, fee_pct: float) -> int:
    return order.amount_cents + apply_percentage(order.amount_cents, fee_pct)


def bulk_total(orders: list[Order]) -> int:
    return sum(o.amount_cents for o in orders)
