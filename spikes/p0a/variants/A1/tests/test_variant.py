from build.cache.types import pack, to_record, unpack
from src.models import Customer


def test_customer_email_roundtrip():
    c = Customer(name="ada", tier="gold", email="ada@example.com")
    rec = to_record(c)
    assert rec.email == "ada@example.com"
    again = unpack(pack(rec))
    assert again.email == "ada@example.com"
