_RATES = {"de": 19.0, "fr": 20.0, "us-ca": 7.25, "jp": 10.0}


def tax_for(amount_cents: int, region: str) -> int:
    rate = _RATES.get(region, 0.0)
    return round(amount_cents * rate / 100.0)


def gross(amount_cents: int, region: str) -> int:
    return amount_cents + tax_for(amount_cents, region)
