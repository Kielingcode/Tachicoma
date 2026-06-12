from datetime import date

from src.lib.dates import add_business_days, quarter_of


def test_add_business_days_skips_weekend():
    assert add_business_days(date(2026, 6, 5), 1) == date(2026, 6, 8)


def test_quarter():
    assert quarter_of(date(2026, 6, 11)) == 2
