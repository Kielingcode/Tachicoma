from build.cache.types import pack, to_record, unpack
from src.models import Customer, Invoice, Order, Shipment


def test_customer_roundtrip():
    c = Customer(name="ada", tier="gold")
    rec = to_record(c)
    assert rec.name == "ada"
    assert rec.tier == "gold"
    again = unpack(pack(rec))
    assert again.name == "ada"
    assert again.tier == "gold"


def test_order_roundtrip():
    o = Order(order_id="o-1", amount_cents=1250)
    rec = to_record(o)
    again = unpack(pack(rec))
    assert again.order_id == "o-1"
    assert again.amount_cents == 1250


def test_invoice_roundtrip():
    i = Invoice(invoice_id="i-9", order_id="o-1", total_cents=1250)
    again = unpack(pack(to_record(i)))
    assert again.invoice_id == "i-9"
    assert again.total_cents == 1250


def test_shipment_roundtrip():
    s = Shipment(shipment_id="s-3", order_id="o-1", carrier="dhl")
    again = unpack(pack(to_record(s)))
    assert again.carrier == "dhl"
