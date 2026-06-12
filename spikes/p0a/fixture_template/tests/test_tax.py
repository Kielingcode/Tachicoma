from src.services.tax import gross, tax_for


def test_tax():
    assert tax_for(1000, "de") == 190


def test_gross_unknown_region():
    assert gross(1000, "nowhere") == 1000
