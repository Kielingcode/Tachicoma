from src.models import Order
from src.services.pricing import bulk_total, order_total_with_fee


def test_fee():
    o = Order(order_id="o-1", amount_cents=1000)
    assert order_total_with_fee(o, 2.5) == 1025


def test_bulk():
    orders = [Order(order_id="o-1", amount_cents=100), Order(order_id="o-2", amount_cents=250)]
    assert bulk_total(orders) == 350
