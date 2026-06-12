from build.cache.types import pack, to_record, unpack
from src.models import Order


def test_order_currency_roundtrip():
    o = Order(order_id="o-7", amount_cents=995, currency="USD")
    rec = to_record(o)
    assert rec.currency == "USD"
    again = unpack(pack(rec))
    assert again.currency == "USD"
